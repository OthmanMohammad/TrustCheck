"""
TrustCheck UN Scraper.

Scrapes the UN Security Council Consolidated Sanctions List.
"""

import logging
from typing import Any

from lxml import etree

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity

logger = logging.getLogger(__name__)


class UNScraper(BaseScraper):
    """Scraper for UN Security Council Consolidated Sanctions List."""

    @property
    def source(self) -> DataSource:
        return DataSource.UN

    @property
    def url(self) -> str:
        return settings.un_consolidated_url

    async def _parse(self, content: bytes) -> list[RawEntity]:
        """Parse UN consolidated list XML content."""
        entities = []

        try:
            root = etree.fromstring(content)

            # Find all INDIVIDUAL and ENTITY entries
            individuals = root.findall(".//INDIVIDUAL")
            if not individuals:
                individuals = root.findall(".//{*}INDIVIDUAL")

            orgs = root.findall(".//ENTITY")
            if not orgs:
                orgs = root.findall(".//{*}ENTITY")

            logger.info(f"Found {len(individuals)} individuals and {len(orgs)} entities")

            # Parse individuals
            for entry in individuals:
                try:
                    entity = self._parse_individual(entry)
                    if entity:
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Error parsing UN individual: {e}")
                    continue

            # Parse organizations/entities
            for entry in orgs:
                try:
                    entity = self._parse_entity(entry)
                    if entity:
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Error parsing UN entity: {e}")
                    continue

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error parsing UN list: {e}")
            raise

        return entities

    def _parse_individual(self, entry: etree._Element) -> RawEntity | None:
        """Parse an individual entry."""
        # Get data ID
        dataid = self._get_text(entry, "DATAID")
        if not dataid:
            return None

        # Get name components
        first_name = self._get_text(entry, "FIRST_NAME") or ""
        second_name = self._get_text(entry, "SECOND_NAME") or ""
        third_name = self._get_text(entry, "THIRD_NAME") or ""
        fourth_name = self._get_text(entry, "FOURTH_NAME") or ""

        # Build primary name
        name_parts = [p for p in [first_name, second_name, third_name, fourth_name] if p]
        if not name_parts:
            return None

        primary_name = " ".join(name_parts)

        # Parse aliases
        names = [{"value": primary_name, "type": "PRIMARY"}]
        aliases = self._parse_aliases(entry)
        names.extend(aliases)

        # Parse programs (UN call numbers)
        programs = self._parse_programs(entry)

        # Parse date of birth
        dob = self._parse_dob(entry)

        # Parse place of birth
        pob = self._parse_pob(entry)

        # Parse nationality
        nationality = self._parse_nationality(entry)

        # Parse addresses
        addresses = self._parse_addresses(entry)

        # Parse identifiers
        identifiers = self._parse_documents(entry)

        # Parse remarks
        remarks = self._get_text(entry, "COMMENTS1")

        # Build raw data
        raw_data = self._entry_to_dict(entry)

        return RawEntity(
            source_uid=dataid,
            primary_name=primary_name,
            entity_type=EntityType.INDIVIDUAL,
            names=names,
            addresses=addresses,
            identifiers=identifiers,
            programs=programs,
            date_of_birth=dob,
            place_of_birth=pob,
            nationality=nationality,
            remarks=remarks,
            raw_data=raw_data,
        )

    def _parse_entity(self, entry: etree._Element) -> RawEntity | None:
        """Parse an entity (organization) entry."""
        dataid = self._get_text(entry, "DATAID")
        if not dataid:
            return None

        # Get name
        first_name = self._get_text(entry, "FIRST_NAME") or ""

        if not first_name:
            return None

        primary_name = first_name

        # Parse aliases
        names = [{"value": primary_name, "type": "PRIMARY"}]
        aliases = self._parse_aliases(entry)
        names.extend(aliases)

        # Parse programs
        programs = self._parse_programs(entry)

        # Parse addresses
        addresses = self._parse_addresses(entry)

        # Parse remarks
        remarks = self._get_text(entry, "COMMENTS1")

        # Build raw data
        raw_data = self._entry_to_dict(entry)

        return RawEntity(
            source_uid=dataid,
            primary_name=primary_name,
            entity_type=EntityType.ORGANIZATION,
            names=names,
            addresses=addresses,
            identifiers=[],
            programs=programs,
            remarks=remarks,
            raw_data=raw_data,
        )

    def _parse_aliases(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse alias entries."""
        aliases = []

        # Individual aliases
        alias_list = entry.find("INDIVIDUAL_ALIAS")
        if alias_list is not None:
            for alias in alias_list.findall("ALIAS_NAME"):
                if alias.text:
                    aliases.append({"value": alias.text.strip(), "type": "ALIAS"})

        # Entity aliases
        alias_list = entry.find("ENTITY_ALIAS")
        if alias_list is not None:
            for alias in alias_list.findall("ALIAS_NAME"):
                if alias.text:
                    aliases.append({"value": alias.text.strip(), "type": "ALIAS"})

        return aliases

    def _parse_programs(self, entry: etree._Element) -> list[str]:
        """Parse UN reference numbers."""
        programs = []

        ref_num = self._get_text(entry, "UN_LIST_TYPE")
        if ref_num:
            programs.append(ref_num)

        ref_num = self._get_text(entry, "REFERENCE_NUMBER")
        if ref_num:
            programs.append(ref_num)

        return programs

    def _parse_dob(self, entry: etree._Element) -> str | None:
        """Parse date of birth."""
        dob_elem = entry.find("INDIVIDUAL_DATE_OF_BIRTH")
        if dob_elem is not None:
            date_elem = dob_elem.find("DATE")
            if date_elem is not None and date_elem.text:
                return date_elem.text.strip()

            year = dob_elem.find("YEAR")
            if year is not None and year.text:
                return year.text.strip()

        return None

    def _parse_pob(self, entry: etree._Element) -> str | None:
        """Parse place of birth."""
        pob_elem = entry.find("INDIVIDUAL_PLACE_OF_BIRTH")
        if pob_elem is not None:
            city = pob_elem.find("CITY")
            country = pob_elem.find("COUNTRY")

            parts = []
            if city is not None and city.text:
                parts.append(city.text.strip())
            if country is not None and country.text:
                parts.append(country.text.strip())

            return ", ".join(parts) if parts else None

        return None

    def _parse_nationality(self, entry: etree._Element) -> str | None:
        """Parse nationality."""
        nat_elem = entry.find("NATIONALITY")
        if nat_elem is not None:
            value = nat_elem.find("VALUE")
            if value is not None and value.text:
                return value.text.strip()

        return None

    def _parse_addresses(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse addresses."""
        addresses = []

        # Individual addresses
        addr_elem = entry.find("INDIVIDUAL_ADDRESS")
        if addr_elem is not None:
            address = self._parse_address_entry(addr_elem)
            if address:
                addresses.append(address)

        # Entity addresses
        addr_elem = entry.find("ENTITY_ADDRESS")
        if addr_elem is not None:
            address = self._parse_address_entry(addr_elem)
            if address:
                addresses.append(address)

        return addresses

    def _parse_address_entry(self, addr_elem: etree._Element) -> dict[str, str] | None:
        """Parse a single address entry."""
        street = self._get_text(addr_elem, "STREET")
        city = self._get_text(addr_elem, "CITY")
        country = self._get_text(addr_elem, "COUNTRY")
        state = self._get_text(addr_elem, "STATE_PROVINCE")
        postal = self._get_text(addr_elem, "ZIP_CODE")
        note = self._get_text(addr_elem, "NOTE")

        parts = [p for p in [street, city, state, postal, country, note] if p]

        if not parts:
            return None

        return {
            "country": country or "",
            "city": city or "",
            "street": street or "",
            "postal_code": postal or "",
            "full_address": ", ".join(parts),
        }

    def _parse_documents(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse identity documents."""
        documents = []

        doc_elem = entry.find("INDIVIDUAL_DOCUMENT")
        if doc_elem is not None:
            doc_type = self._get_text(doc_elem, "TYPE_OF_DOCUMENT")
            doc_number = self._get_text(doc_elem, "NUMBER")
            doc_country = self._get_text(doc_elem, "ISSUING_COUNTRY")

            if doc_number:
                documents.append(
                    {
                        "type": self._map_doc_type(doc_type),
                        "value": doc_number,
                        "country": doc_country or "",
                    }
                )

        return documents

    def _map_doc_type(self, doc_type: str | None) -> str:
        """Map UN document type to standard type."""
        if not doc_type:
            return "OTHER"

        doc_type_upper = doc_type.upper()

        if "PASSPORT" in doc_type_upper:
            return "PASSPORT"
        elif "NATIONAL" in doc_type_upper:
            return "NATIONAL_ID"
        else:
            return "OTHER"

    def _get_text(self, element: etree._Element, tag: str) -> str | None:
        """Get text content of a child element."""
        child = element.find(tag)
        if child is None:
            child = element.find(f"{{*}}{tag}")

        if child is not None and child.text:
            return self._clean_text(child.text)

        return None

    def _entry_to_dict(self, entry: etree._Element) -> dict[str, Any]:
        """Convert XML element to dictionary for raw storage."""
        result: dict[str, Any] = {}

        for child in entry:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if len(child) > 0:
                result[tag] = self._entry_to_dict(child)
            else:
                result[tag] = child.text

        return result
