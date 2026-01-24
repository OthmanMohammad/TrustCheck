"""
TrustCheck UK Scraper.

Scrapes the UK HM Treasury Consolidated Sanctions List.
The UK list is provided in ODS (OpenDocument Spreadsheet) format.
"""

import io
import logging
from typing import Any

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity

logger = logging.getLogger(__name__)


class UKScraper(BaseScraper):
    """Scraper for UK HM Treasury Consolidated Sanctions List."""

    @property
    def source(self) -> DataSource:
        return DataSource.UK

    @property
    def url(self) -> str:
        return settings.uk_sanctions_url

    async def _parse(self, content: bytes) -> list[RawEntity]:
        """Parse UK sanctions list ODS content."""
        entities = []

        try:
            # Try to parse as ODS file
            try:
                import pandas as pd

                # Read ODS file
                df = pd.read_excel(io.BytesIO(content), engine="odf", sheet_name=0)
                entities = self._parse_dataframe(df)
            except ImportError:
                # Fallback: try xlsx
                import pandas as pd

                df = pd.read_excel(io.BytesIO(content), engine="openpyxl", sheet_name=0)
                entities = self._parse_dataframe(df)

        except Exception as e:
            logger.error(f"Error parsing UK list: {e}")
            # Try alternative URL with xlsx format
            try:
                import pandas as pd

                xlsx_url = settings.uk_sanctions_url.replace(".ods", ".xlsx")
                logger.info(f"Trying alternative xlsx format: {xlsx_url}")
                df = pd.read_excel(io.BytesIO(content), engine="openpyxl", sheet_name=0)
                entities = self._parse_dataframe(df)
            except Exception as e2:
                logger.error(f"Error parsing UK list (xlsx fallback): {e2}")
                raise

        return entities

    def _parse_dataframe(self, df: Any) -> list[RawEntity]:
        """Parse a pandas DataFrame into entities."""
        entities = []

        # Normalize column names
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

        logger.info(f"UK list columns: {list(df.columns)}")

        # Common column name mappings
        col_mappings = {
            "name_1": ["name_1", "name1", "primary_name", "name"],
            "name_2": ["name_2", "name2", "name_part_2"],
            "name_3": ["name_3", "name3", "name_part_3"],
            "name_4": ["name_4", "name4", "name_part_4"],
            "name_5": ["name_5", "name5", "name_part_5"],
            "name_6": ["name_6", "name6", "name_part_6"],
            "type": ["group_type", "type", "entity_type"],
            "dob": ["dob", "date_of_birth", "dateofbirth"],
            "pob": ["town_of_birth", "place_of_birth", "placeofbirth"],
            "country": ["country_of_birth", "nationality", "country"],
            "regime": ["regime", "sanctions_regime", "program"],
            "uid": ["group_id", "unique_id", "id", "reference"],
            "alias": ["alias", "aliases", "aka", "also_known_as"],
            "address": ["address", "address_1", "full_address"],
            "passport": ["passport_details", "passport_number", "passport"],
            "national_id": ["national_identification_number", "national_id", "id_number"],
        }

        def get_column(row: Any, key: str) -> str | None:
            """Get column value using mapping."""
            for col_name in col_mappings.get(key, [key]):
                if col_name in row.index:
                    val = row[col_name]
                    if pd.notna(val):
                        return str(val).strip()
            return None

        # Import pandas for notna check
        import pandas as pd

        for _, row in df.iterrows():
            try:
                # Get unique ID
                uid = get_column(row, "uid")
                if not uid:
                    uid = str(row.name)  # Use row index as fallback

                # Get name parts
                name_parts = []
                for i in range(1, 7):
                    name_part = get_column(row, f"name_{i}")
                    if name_part:
                        name_parts.append(name_part)

                if not name_parts:
                    continue

                primary_name = " ".join(name_parts)

                # Determine entity type
                type_str = get_column(row, "type")
                entity_type = self._map_type(type_str)

                # Get aliases
                names = [{"value": primary_name, "type": "PRIMARY"}]
                alias_str = get_column(row, "alias")
                if alias_str:
                    for alias in alias_str.split(";"):
                        alias = alias.strip()
                        if alias and alias != primary_name:
                            names.append({"value": alias, "type": "ALIAS"})

                # Get programs
                programs = []
                regime = get_column(row, "regime")
                if regime:
                    programs = [p.strip() for p in regime.split(";") if p.strip()]

                # Get date of birth
                dob = get_column(row, "dob")

                # Get place of birth
                pob = get_column(row, "pob")

                # Get nationality
                nationality = get_column(row, "country")

                # Get addresses
                addresses = []
                address = get_column(row, "address")
                if address:
                    addresses.append(
                        {
                            "country": nationality or "",
                            "city": "",
                            "street": "",
                            "postal_code": "",
                            "full_address": address,
                        }
                    )

                # Get identifiers
                identifiers = []
                passport = get_column(row, "passport")
                if passport:
                    identifiers.append(
                        {
                            "type": "PASSPORT",
                            "value": passport,
                            "country": nationality or "",
                        }
                    )

                national_id = get_column(row, "national_id")
                if national_id:
                    identifiers.append(
                        {
                            "type": "NATIONAL_ID",
                            "value": national_id,
                            "country": nationality or "",
                        }
                    )

                # Build raw data
                raw_data = {col: str(val) if pd.notna(val) else None for col, val in row.items()}

                entities.append(
                    RawEntity(
                        source_uid=uid,
                        primary_name=primary_name,
                        entity_type=entity_type,
                        names=names,
                        addresses=addresses,
                        identifiers=identifiers,
                        programs=programs,
                        date_of_birth=dob,
                        place_of_birth=pob,
                        nationality=nationality,
                        raw_data=raw_data,
                    )
                )

            except Exception as e:
                logger.warning(f"Error parsing UK row: {e}")
                continue

        logger.info(f"Parsed {len(entities)} entities from UK list")
        return entities

    def _map_type(self, type_str: str | None) -> EntityType:
        """Map UK type to EntityType."""
        if not type_str:
            return EntityType.UNKNOWN

        type_lower = type_str.lower()

        if "individual" in type_lower or "person" in type_lower:
            return EntityType.INDIVIDUAL
        elif "entity" in type_lower or "ship" not in type_lower:
            return EntityType.ORGANIZATION
        elif "ship" in type_lower:
            return EntityType.VESSEL
        else:
            return EntityType.UNKNOWN
