"""
TrustCheck UK Scraper.

Scrapes the UK FCDO Sanctions List (XML format).
The UK list is provided in XML format with a static URL.
"""

import logging
from typing import Any

from lxml import etree

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity

logger = logging.getLogger(__name__)


class UKScraper(BaseScraper):
    """Scraper for UK FCDO Sanctions List (XML format)."""

    @property
    def source(self) -> DataSource:
        return DataSource.UK

    @property
    def url(self) -> str:
        return settings.uk_sanctions_url

    async def _parse(self, content: bytes) -> list[RawEntity]:
        """Parse UK sanctions list XML content."""
        entities = []

        try:
            root = etree.fromstring(content)

            # Find all Designation entries (Individuals, Entities, Ships)
            # UK XML structure: Designations/Designation
            designations = root.findall(".//Designation")
            if not designations:
                designations = root.findall(".//{*}Designation")

            # Also try alternative paths
            if not designations:
                designations = root.findall(".//Individual") + root.findall(".//Entity") + root.findall(".//Ship")
            if not designations:
                designations = root.findall(".//{*}Individual") + root.findall(".//{*}Entity") + root.findall(".//{*}Ship")

            logger.info(f"Found {len(designations)} UK designations")

            for entry in designations:
                try:
                    entity = self._parse_entry(entry)
                    if entity:
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Error parsing UK entity: {e}")
                    continue

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error parsing UK list: {e}")
            raise

        return entities

    def _parse_entry(self, entry: etree._Element) -> RawEntity | None:
        """Parse a single Designation entry."""
        # Get unique ID
        uid = self._get_text(entry, "UniqueID")
        if not uid:
            uid = self._get_text(entry, "OFSIGroupID")
        if not uid:
            uid = entry.get("UniqueID") or entry.get("id")
        if not uid:
            return None

        # Determine entity type based on tag or GroupTypeDescription
        tag_name = entry.tag.split("}")[-1] if "}" in entry.tag else entry.tag
        group_type = self._get_text(entry, "GroupTypeDescription") or tag_name

        entity_type = self._map_type(group_type)

        # Get names
        names = self._parse_names(entry)
        if not names:
            return None

        primary_name = names[0]["value"]

        # Get regime/programs
        programs = self._parse_regimes(entry)

        # Get addresses
        addresses = self._parse_addresses(entry)

        # Get identifiers (passports, national IDs)
        identifiers = self._parse_identifiers(entry)

        # Get birth info
        dob, pob = self._parse_birth_info(entry)

        # Get nationality
        nationality = self._parse_nationality(entry)

        # Get remarks
        remarks = self._get_text(entry, "OtherInformation") or self._get_text(entry, "Remarks")

        # Build raw data
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

    def _get_text(self, element: etree._Element, tag: str) -> str | None:
        """Get text from a child element."""
        child = element.find(f".//{tag}")
        if child is None:
            # Try with wildcard namespace
            child = element.find(".//{*}" + tag)
        if child is not None and child.text:
            return self._clean_text(child.text)
        return None

    def _parse_names(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse name entries from UK format."""
        names = []

        # Try to find Names element with Name1-Name6
        names_elem = entry.find(".//Names")
        if names_elem is None:
            names_elem = entry

        # UK format uses Name1-Name6 (Last name is typically Name6)
        name_parts = []
        for i in range(1, 7):
            name_val = self._get_text(names_elem, f"Name{i}")
            if name_val:
                name_parts.append(name_val)

        if name_parts:
            # In UK format, Name6 is often the surname
            # Construct full name: Name1 Name2 Name3 Name4 Name5 Name6
            primary_name = " ".join(name_parts)
            names.append({"value": primary_name.strip(), "type": "PRIMARY"})

        # Also check for wholeName or primaryName
        whole_name = self._get_text(entry, "WholeName") or self._get_text(entry, "PrimaryName")
        if whole_name and whole_name not in [n["value"] for n in names]:
            if not names:
                names.append({"value": whole_name, "type": "PRIMARY"})
            else:
                names.append({"value": whole_name, "type": "ALIAS"})

        # Parse aliases (AKA)
        alias_elements = entry.findall(".//Alias") or entry.findall(".//{*}Alias")
        for alias in alias_elements:
            alias_name = alias.text or alias.get("WholeName")
            if not alias_name:
                # Try Name1-Name6 within alias
                alias_parts = []
                for i in range(1, 7):
                    part = self._get_text(alias, f"Name{i}")
                    if part:
                        alias_parts.append(part)
                if alias_parts:
                    alias_name = " ".join(alias_parts)

            if alias_name:
                alias_type = alias.get("AliasType") or alias.get("Quality") or "ALIAS"
                if "low" in alias_type.lower():
                    alias_type = "WEAK_ALIAS"
                else:
                    alias_type = "ALIAS"
                names.append({"value": alias_name.strip(), "type": alias_type})

        # Also try AKA elements
        aka_elements = entry.findall(".//AKA") or entry.findall(".//{*}AKA")
        for aka in aka_elements:
            aka_name = aka.text
            if aka_name and aka_name not in [n["value"] for n in names]:
                names.append({"value": aka_name.strip(), "type": "ALIAS"})

        return names

    def _parse_regimes(self, entry: etree._Element) -> list[str]:
        """Parse sanctions regimes."""
        programs = []

        # Try Regime elements
        regime_elements = entry.findall(".//Regime") or entry.findall(".//{*}Regime")
        for regime in regime_elements:
            regime_name = regime.text or regime.get("RegimeName")
            if regime_name:
                programs.append(regime_name.strip())

        # Try SanctionsRegime
        regime_name = self._get_text(entry, "SanctionsRegime") or self._get_text(entry, "RegimeName")
        if regime_name and regime_name not in programs:
            programs.append(regime_name)

        # Try UKSanctionsListRef
        uk_ref = self._get_text(entry, "UKSanctionsListRef")
        if uk_ref and uk_ref not in programs:
            programs.append(uk_ref)

        return programs

    def _parse_addresses(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse address entries."""
        addresses = []

        addr_elements = entry.findall(".//Address") or entry.findall(".//{*}Address")
        for addr in addr_elements:
            street = self._get_text(addr, "AddressLine1") or self._get_text(addr, "Street")
            city = self._get_text(addr, "AddressCity") or self._get_text(addr, "City")
            postal = self._get_text(addr, "AddressPostalCode") or self._get_text(addr, "PostalCode")
            country = self._get_text(addr, "AddressCountry") or self._get_text(addr, "Country")

            # Build full address
            parts = []
            for line_num in range(1, 7):
                line = self._get_text(addr, f"AddressLine{line_num}")
                if line:
                    parts.append(line)
            if city:
                parts.append(city)
            if postal:
                parts.append(postal)
            if country:
                parts.append(country)

            if parts:
                addresses.append({
                    "country": country or "",
                    "city": city or "",
                    "street": street or "",
                    "postal_code": postal or "",
                    "full_address": ", ".join(parts),
                })

        return addresses

    def _parse_identifiers(self, entry: etree._Element) -> list[dict[str, str]]:
        """Parse identification documents."""
        identifiers = []

        # Passport numbers
        passport_elements = entry.findall(".//PassportNumber") or entry.findall(".//{*}PassportNumber")
        for passport in passport_elements:
            number = passport.text or passport.get("Number")
            if number:
                identifiers.append({
                    "type": "PASSPORT",
                    "value": number.strip(),
                    "country": passport.get("Country") or "",
                })

        # Also try PassportDetails
        passport_details = self._get_text(entry, "PassportDetails")
        if passport_details:
            identifiers.append({
                "type": "PASSPORT",
                "value": passport_details,
                "country": "",
            })

        # National identification
        nat_id_elements = entry.findall(".//NationalIdentifierNumber") or entry.findall(".//{*}NationalIdentifierNumber")
        for nat_id in nat_id_elements:
            number = nat_id.text or nat_id.get("Number")
            if number:
                identifiers.append({
                    "type": "NATIONAL_ID",
                    "value": number.strip(),
                    "country": nat_id.get("Country") or "",
                })

        # Also try NationalIdentifierDetails
        nat_id_details = self._get_text(entry, "NationalIdentifierDetails")
        if nat_id_details:
            identifiers.append({
                "type": "NATIONAL_ID",
                "value": nat_id_details,
                "country": "",
            })

        return identifiers

    def _parse_birth_info(self, entry: etree._Element) -> tuple[str | None, str | None]:
        """Parse birth date and place."""
        dob = None
        pob = None

        # Date of birth
        dob_elem = entry.find(".//DOB") or entry.find(".//{*}DOB")
        if dob_elem is not None:
            dob = dob_elem.text or dob_elem.get("Date")

        if not dob:
            dob = self._get_text(entry, "DateOfBirth") or self._get_text(entry, "BirthDate")

        # Place of birth
        pob = self._get_text(entry, "TownOfBirth") or self._get_text(entry, "PlaceOfBirth")
        country_of_birth = self._get_text(entry, "CountryOfBirth")
        if pob and country_of_birth:
            pob = f"{pob}, {country_of_birth}"
        elif country_of_birth:
            pob = country_of_birth

        return dob, pob

    def _parse_nationality(self, entry: etree._Element) -> str | None:
        """Parse nationality."""
        nationality = self._get_text(entry, "Nationality")
        if not nationality:
            nationality = self._get_text(entry, "Country")
        return nationality

    def _map_type(self, type_str: str | None) -> EntityType:
        """Map UK type to EntityType."""
        if not type_str:
            return EntityType.UNKNOWN

        type_lower = type_str.lower()

        if "individual" in type_lower or "person" in type_lower:
            return EntityType.INDIVIDUAL
        elif "ship" in type_lower or "vessel" in type_lower:
            return EntityType.VESSEL
        elif "aircraft" in type_lower:
            return EntityType.AIRCRAFT
        elif "entity" in type_lower or "organisation" in type_lower or "organization" in type_lower:
            return EntityType.ORGANIZATION
        else:
            return EntityType.UNKNOWN

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
