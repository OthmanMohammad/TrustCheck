"""
TrustCheck EU Scraper.

Scrapes the EU Financial Sanctions (FSF) Consolidated List.
"""

import logging
from typing import Any

from lxml import etree

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity

logger = logging.getLogger(__name__)


class EUScraper(BaseScraper):
    """Scraper for EU Financial Sanctions Consolidated List."""

    @property
    def source(self) -> DataSource:
        return DataSource.EU

    @property
    def url(self) -> str:
        return settings.eu_sanctions_url

    async def _parse(self, content: bytes) -> list[RawEntity]:
        """Parse EU sanctions list XML content."""
        entities = []

        try:
            root = etree.fromstring(content)

            # Find all sanctionEntity elements
            sanction_entities = root.findall(".//sanctionEntity")
            if not sanction_entities:
                sanction_entities = root.findall(".//{*}sanctionEntity")

            logger.info(f"Found {len(sanction_entities)} EU sanction entities")

            for entry in sanction_entities:
                try:
                    entity = self._parse_entry(entry)
                    if entity:
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Error parsing EU entity: {e}")
                    continue

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error parsing EU list: {e}")
            raise

        return entities

    def _parse_entry(self, entry: etree._Element) -> RawEntity | None:
        """Parse a single sanctionEntity entry."""
        # Get logical ID
        logical_id = entry.get("logicalId")
        if not logical_id:
            logical_id = entry.get("euReferenceNumber")
        if not logical_id:
            return None

        # Determine entity type
        subject_type = entry.find(".//subjectType")
        if subject_type is None:
            subject_type = entry.find(".//{*}subjectType")

        if subject_type is not None:
            code = subject_type.get("code") or subject_type.text
            entity_type = self._map_subject_type(code)
        else:
            entity_type = EntityType.UNKNOWN

        # Get names
        names = self._parse_names(entry)
        if not names:
            return None

        primary_name = names[0]["value"]

        # Get programs (regulations)
        programs = self._parse_regulations(entry)

        # Get addresses
        addresses = self._parse_addresses(entry)

        # Get identifiers
        identifiers = self._parse_identifications(entry)

        # Get birth info
        dob, pob = self._parse_birth_info(entry)

        # Get citizenship/nationality
        nationality = self._parse_citizenship(entry)

        # Get remarks
        remarks = self._parse_remarks(entry)

        # Build raw data
        raw_data = self._entry_to_dict(entry)

        return RawEntity(
            source_uid=logical_id,
            primary_name=primary_name,
            entity_type=entity_type,
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

    def _map_subject_type(self, code: str | None) -> EntityType:
        """Map EU subject type to EntityType."""
        if not code:
            return EntityType.UNKNOWN

        code_lower = code.lower()

        if "person" in code_lower:
            return EntityType.INDIVIDUAL
        elif "enterprise" in code_lower or "entity" in code_lower:
            return EntityType.ORGANIZATION
        else:
            return EntityType.UNKNOWN

    def _parse_names(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse name entries."""
        names = []

        # Find nameAlias elements
        name_aliases = entry.findall(".//nameAlias")
        if not name_aliases:
            name_aliases = entry.findall(".//{*}nameAlias")

        for alias in name_aliases:
            whole_name = alias.get("wholeName")
            if not whole_name:
                # Try to build from components
                first = alias.get("firstName") or ""
                middle = alias.get("middleName") or ""
                last = alias.get("lastName") or ""
                parts = [p for p in [first, middle, last] if p]
                whole_name = " ".join(parts)

            if whole_name:
                name_type = "PRIMARY" if not names else "ALIAS"
                strong = alias.get("strong") == "true"
                if strong:
                    name_type = "PRIMARY"
                names.append({"value": whole_name.strip(), "type": name_type})

        return names

    def _parse_regulations(self, entry: etree._Element) -> list[str]:
        """Parse regulation references."""
        programs = []

        regulations = entry.findall(".//regulation")
        if not regulations:
            regulations = entry.findall(".//{*}regulation")

        for reg in regulations:
            programme = reg.get("programme")
            if programme:
                programs.append(programme)

            reg_type = reg.get("regulationType")
            if reg_type and reg_type not in programs:
                programs.append(reg_type)

        return programs

    def _parse_addresses(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse address entries."""
        addresses = []

        addr_elements = entry.findall(".//address")
        if not addr_elements:
            addr_elements = entry.findall(".//{*}address")

        for addr in addr_elements:
            street = addr.get("street")
            city = addr.get("city")
            zipcode = addr.get("zipCode")
            country = addr.get("countryIso2Code") or addr.get("countryDescription")

            parts = [p for p in [street, city, zipcode, country] if p]

            if parts:
                addresses.append(
                    {
                        "country": country or "",
                        "city": city or "",
                        "street": street or "",
                        "postal_code": zipcode or "",
                        "full_address": ", ".join(parts),
                    }
                )

        return addresses

    def _parse_identifications(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse identification documents."""
        identifiers = []

        id_elements = entry.findall(".//identification")
        if not id_elements:
            id_elements = entry.findall(".//{*}identification")

        for id_elem in id_elements:
            id_type = id_elem.get("identificationTypeCode") or id_elem.get("identificationTypeDescription")
            number = id_elem.get("number") or id_elem.get("diplomaticPassport")
            country = id_elem.get("countryIso2Code")
            issue_date = id_elem.get("issueDate")
            valid_to = id_elem.get("validTo")

            if number:
                identifiers.append(
                    {
                        "type": self._map_id_type(id_type),
                        "value": number,
                        "country": country or "",
                        "issue_date": issue_date or "",
                        "expiry_date": valid_to or "",
                    }
                )

        return identifiers

    def _map_id_type(self, id_type: str | None) -> str:
        """Map EU identification type to standard type."""
        if not id_type:
            return "OTHER"

        id_type_lower = id_type.lower()

        if "passport" in id_type_lower:
            return "PASSPORT"
        elif "national" in id_type_lower:
            return "NATIONAL_ID"
        elif "tax" in id_type_lower:
            return "TAX_ID"
        elif "registration" in id_type_lower:
            return "REGISTRATION_NUMBER"
        else:
            return "OTHER"

    def _parse_birth_info(self, entry: etree._Element) -> tuple[str | None, str | None]:
        """Parse birth date and place."""
        dob = None
        pob = None

        birth_elements = entry.findall(".//birthdate")
        if not birth_elements:
            birth_elements = entry.findall(".//{*}birthdate")

        for birth in birth_elements:
            if not dob:
                dob = birth.get("birthdate")
                if not dob:
                    year = birth.get("year")
                    month = birth.get("month")
                    day = birth.get("day")
                    if year:
                        dob = year
                        if month:
                            dob = f"{year}-{month}"
                            if day:
                                dob = f"{year}-{month}-{day}"

            if not pob:
                city = birth.get("city")
                country = birth.get("countryIso2Code") or birth.get("countryDescription")
                parts = [p for p in [city, country] if p]
                if parts:
                    pob = ", ".join(parts)

        return dob, pob

    def _parse_citizenship(self, entry: etree._Element) -> str | None:
        """Parse citizenship/nationality."""
        citizen_elements = entry.findall(".//citizenship")
        if not citizen_elements:
            citizen_elements = entry.findall(".//{*}citizenship")

        for citizen in citizen_elements:
            country = citizen.get("countryIso2Code") or citizen.get("countryDescription")
            if country:
                return country

        return None

    def _parse_remarks(self, entry: etree._Element) -> str | None:
        """Parse remarks/comments."""
        remark_elem = entry.find(".//remark")
        if remark_elem is None:
            remark_elem = entry.find(".//{*}remark")

        if remark_elem is not None and remark_elem.text:
            return self._clean_text(remark_elem.text)

        return None

    def _entry_to_dict(self, entry: etree._Element) -> dict[str, Any]:
        """Convert XML element to dictionary for raw storage."""
        result: dict[str, Any] = {"attributes": dict(entry.attrib)}

        for child in entry:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if len(child) > 0:
                if tag in result:
                    if not isinstance(result[tag], list):
                        result[tag] = [result[tag]]
                    result[tag].append(self._entry_to_dict(child))
                else:
                    result[tag] = self._entry_to_dict(child)
            else:
                child_data = dict(child.attrib)
                if child.text:
                    child_data["text"] = child.text
                if tag in result:
                    if not isinstance(result[tag], list):
                        result[tag] = [result[tag]]
                    result[tag].append(child_data)
                else:
                    result[tag] = child_data

        return result
