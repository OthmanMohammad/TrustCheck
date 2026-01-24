"""
TrustCheck OFAC SDN Scraper.

Scrapes the OFAC Specially Designated Nationals (SDN) list.
"""

import logging
from typing import Any

from lxml import etree

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity

logger = logging.getLogger(__name__)

# XML namespaces used in OFAC SDN
NAMESPACES = {
    "sdn": "http://www.un.org/sanctions/1.0",
}


class OFACScraper(BaseScraper):
    """Scraper for OFAC SDN (Specially Designated Nationals) list."""

    @property
    def source(self) -> DataSource:
        return DataSource.OFAC_SDN

    @property
    def url(self) -> str:
        return settings.ofac_sdn_url

    async def _parse(self, content: bytes) -> list[RawEntity]:
        """Parse OFAC SDN XML content."""
        entities = []

        try:
            # Parse XML (handle both namespace and non-namespace versions)
            root = etree.fromstring(content)

            # Try different root element names
            sdn_entries = root.findall(".//sdnEntry")
            if not sdn_entries:
                sdn_entries = root.findall(".//{*}sdnEntry")
            if not sdn_entries:
                # Try without namespace
                sdn_entries = list(root.iter("sdnEntry"))

            logger.info(f"Found {len(sdn_entries)} SDN entries")

            for entry in sdn_entries:
                try:
                    entity = self._parse_entry(entry)
                    if entity:
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Error parsing SDN entry: {e}")
                    continue

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error parsing OFAC SDN: {e}")
            raise

        return entities

    def _parse_entry(self, entry: etree._Element) -> RawEntity | None:
        """Parse a single SDN entry."""
        # Get UID
        uid_elem = entry.find("uid")
        if uid_elem is None:
            uid_elem = entry.find("{*}uid")
        uid = uid_elem.text if uid_elem is not None else None

        if not uid:
            return None

        # Get SDN type
        sdn_type_elem = entry.find("sdnType")
        if sdn_type_elem is None:
            sdn_type_elem = entry.find("{*}sdnType")
        sdn_type = sdn_type_elem.text if sdn_type_elem is not None else None

        # Determine entity type
        entity_type = self._map_sdn_type(sdn_type)

        # Get primary name
        first_name = self._get_text(entry, "firstName")
        last_name = self._get_text(entry, "lastName")

        if last_name:
            if first_name:
                primary_name = f"{first_name} {last_name}"
            else:
                primary_name = last_name
        else:
            return None

        # Get programs
        programs = self._parse_programs(entry)

        # Get aliases (AKA list)
        names = self._parse_aliases(entry, primary_name)

        # Get addresses
        addresses = self._parse_addresses(entry)

        # Get IDs
        identifiers = self._parse_ids(entry)

        # Get date of birth
        dob = self._parse_dob(entry)

        # Get place of birth
        pob = self._parse_pob(entry)

        # Get nationality
        nationality = self._parse_nationality(entry)

        # Get remarks
        remarks = self._get_text(entry, "remarks")

        # Build raw data for storage
        raw_data = self._entry_to_dict(entry)

        return RawEntity(
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
            remarks=remarks,
            raw_data=raw_data,
        )

    def _map_sdn_type(self, sdn_type: str | None) -> EntityType:
        """Map OFAC SDN type to EntityType."""
        if not sdn_type:
            return EntityType.UNKNOWN

        sdn_type_upper = sdn_type.upper()

        if sdn_type_upper == "INDIVIDUAL":
            return EntityType.INDIVIDUAL
        elif sdn_type_upper == "ENTITY":
            return EntityType.ORGANIZATION
        elif sdn_type_upper == "VESSEL":
            return EntityType.VESSEL
        elif sdn_type_upper == "AIRCRAFT":
            return EntityType.AIRCRAFT
        else:
            return EntityType.UNKNOWN

    def _parse_programs(self, entry: etree._Element) -> list[str]:
        """Parse sanctions programs."""
        programs = []

        program_list = entry.find("programList")
        if program_list is None:
            program_list = entry.find("{*}programList")

        if program_list is not None:
            for program in program_list.findall("program"):
                if program.text:
                    programs.append(program.text.strip())
            for program in program_list.findall("{*}program"):
                if program.text:
                    programs.append(program.text.strip())

        return programs

    def _parse_aliases(self, entry: etree._Element, primary_name: str) -> list[dict[str, str]]:
        """Parse AKA (Also Known As) names."""
        names = [{"value": primary_name, "type": "PRIMARY"}]

        aka_list = entry.find("akaList")
        if aka_list is None:
            aka_list = entry.find("{*}akaList")

        if aka_list is not None:
            for aka in aka_list.findall("aka"):
                name = self._parse_aka_entry(aka)
                if name:
                    names.append(name)
            for aka in aka_list.findall("{*}aka"):
                name = self._parse_aka_entry(aka)
                if name:
                    names.append(name)

        return names

    def _parse_aka_entry(self, aka: etree._Element) -> dict[str, str] | None:
        """Parse a single AKA entry."""
        aka_type = self._get_text(aka, "type") or "ALIAS"

        first_name = self._get_text(aka, "firstName")
        last_name = self._get_text(aka, "lastName")

        if last_name:
            if first_name:
                name_value = f"{first_name} {last_name}"
            else:
                name_value = last_name
            return {"value": name_value, "type": aka_type.upper()}

        return None

    def _parse_addresses(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse addresses."""
        addresses = []

        address_list = entry.find("addressList")
        if address_list is None:
            address_list = entry.find("{*}addressList")

        if address_list is not None:
            for addr in address_list.findall("address"):
                address = self._parse_address_entry(addr)
                if address:
                    addresses.append(address)
            for addr in address_list.findall("{*}address"):
                address = self._parse_address_entry(addr)
                if address:
                    addresses.append(address)

        return addresses

    def _parse_address_entry(self, addr: etree._Element) -> dict[str, str] | None:
        """Parse a single address entry."""
        country = self._get_text(addr, "country")
        city = self._get_text(addr, "city")
        address1 = self._get_text(addr, "address1")
        address2 = self._get_text(addr, "address2")
        address3 = self._get_text(addr, "address3")
        postal_code = self._get_text(addr, "postalCode")
        state = self._get_text(addr, "stateOrProvince")

        # Build full address
        parts = [p for p in [address1, address2, address3, city, state, postal_code, country] if p]

        if not parts:
            return None

        return {
            "country": country or "",
            "city": city or "",
            "street": ", ".join([p for p in [address1, address2, address3] if p]) or "",
            "postal_code": postal_code or "",
            "full_address": ", ".join(parts),
        }

    def _parse_ids(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse identification documents."""
        identifiers = []

        id_list = entry.find("idList")
        if id_list is None:
            id_list = entry.find("{*}idList")

        if id_list is not None:
            for id_elem in id_list.findall("id"):
                identifier = self._parse_id_entry(id_elem)
                if identifier:
                    identifiers.append(identifier)
            for id_elem in id_list.findall("{*}id"):
                identifier = self._parse_id_entry(id_elem)
                if identifier:
                    identifiers.append(identifier)

        return identifiers

    def _parse_id_entry(self, id_elem: etree._Element) -> dict[str, str] | None:
        """Parse a single ID entry."""
        id_type = self._get_text(id_elem, "idType")
        id_number = self._get_text(id_elem, "idNumber")
        id_country = self._get_text(id_elem, "idCountry")
        issue_date = self._get_text(id_elem, "issueDate")
        expiry_date = self._get_text(id_elem, "expirationDate")

        if not id_number:
            return None

        return {
            "type": self._map_id_type(id_type),
            "value": id_number,
            "country": id_country or "",
            "issue_date": issue_date or "",
            "expiry_date": expiry_date or "",
        }

    def _map_id_type(self, id_type: str | None) -> str:
        """Map OFAC ID type to standard type."""
        if not id_type:
            return "OTHER"

        id_type_upper = id_type.upper()

        mapping = {
            "PASSPORT": "PASSPORT",
            "NATIONAL ID": "NATIONAL_ID",
            "SSN": "SSN",
            "TAX ID": "TAX_ID",
            "DRIVER'S LICENSE": "DRIVER_LICENSE",
            "CEDULA NO.": "NATIONAL_ID",
            "NIT #": "TAX_ID",
            "D-U-N-S NUMBER": "REGISTRATION_NUMBER",
            "VESSEL REGISTRATION": "REGISTRATION_NUMBER",
            "IMO": "IMO",
            "MMSI": "MMSI",
            "AIRCRAFT SERIAL": "REGISTRATION_NUMBER",
        }

        for key, value in mapping.items():
            if key in id_type_upper:
                return value

        return "OTHER"

    def _parse_dob(self, entry: etree._Element) -> str | None:
        """Parse date of birth."""
        dob_list = entry.find("dateOfBirthList")
        if dob_list is None:
            dob_list = entry.find("{*}dateOfBirthList")

        if dob_list is not None:
            dob_item = dob_list.find("dateOfBirthItem")
            if dob_item is None:
                dob_item = dob_list.find("{*}dateOfBirthItem")

            if dob_item is not None:
                dob = self._get_text(dob_item, "dateOfBirth")
                return dob

        return None

    def _parse_pob(self, entry: etree._Element) -> str | None:
        """Parse place of birth."""
        pob_list = entry.find("placeOfBirthList")
        if pob_list is None:
            pob_list = entry.find("{*}placeOfBirthList")

        if pob_list is not None:
            pob_item = pob_list.find("placeOfBirthItem")
            if pob_item is None:
                pob_item = pob_list.find("{*}placeOfBirthItem")

            if pob_item is not None:
                pob = self._get_text(pob_item, "placeOfBirth")
                return pob

        return None

    def _parse_nationality(self, entry: etree._Element) -> str | None:
        """Parse nationality."""
        nat_list = entry.find("nationalityList")
        if nat_list is None:
            nat_list = entry.find("{*}nationalityList")

        if nat_list is not None:
            nat_item = nat_list.find("nationality")
            if nat_item is None:
                nat_item = nat_list.find("{*}nationality")

            if nat_item is not None:
                country = self._get_text(nat_item, "country")
                return country

        return None

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
                # Has children
                if tag.endswith("List"):
                    result[tag] = [self._entry_to_dict(c) for c in child]
                else:
                    result[tag] = self._entry_to_dict(child)
            else:
                result[tag] = child.text

        return result
