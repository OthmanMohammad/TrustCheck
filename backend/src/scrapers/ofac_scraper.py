"""
OFAC SDN List Scraper

Downloads and parses the real OFAC Specially Designated Nationals (SDN) list
from the U.S. Treasury Department.
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class SanctionedEntity:
    """Represents a sanctioned entity from OFAC."""
    uid: str
    name: str
    entity_type: str  # "Person" or "Entity"
    programs: List[str]
    addresses: List[str]
    aliases: List[str]
    dates_of_birth: List[str]
    places_of_birth: List[str]
    nationalities: List[str]
    remarks: str
    source: str = "OFAC"
    last_updated: datetime = None

class OFACScraper:
    """Scrapes OFAC SDN list and parses entities."""
    
    SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrustCheck-Compliance-Platform/1.0'
        })
    
    def download_sdn_list(self) -> str:
        """
        Download the OFAC SDN XML file.
        
        Returns:
            Raw XML content as string.
            
        Raises:
            requests.RequestException: If download fails.
        """
        logger.info(f"Downloading OFAC SDN list from {self.SDN_URL}")
        
        try:
            response = self.session.get(self.SDN_URL, timeout=60)
            response.raise_for_status()
            
            logger.info(f"Successfully downloaded SDN list ({len(response.content)} bytes)")
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Failed to download SDN list: {e}")
            raise
    
    def parse_entities(self, xml_content: str) -> List[SanctionedEntity]:
        """
        Parse XML content and extract sanctioned entities.
        
        Args:
            xml_content: Raw XML content from OFAC.
            
        Returns:
            List of SanctionedEntity objects.
        """
        logger.info("Parsing OFAC XML content")
        
        try:
            root = ET.fromstring(xml_content)
            entities = []
            
            # Find all SDN entries
            for sdn_entry in root.findall('.//sdnEntry'):
                entity = self._parse_sdn_entry(sdn_entry)
                if entity:
                    entities.append(entity)
            
            logger.info(f"Parsed {len(entities)} entities from OFAC SDN list")
            return entities
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise
    
    def _parse_sdn_entry(self, sdn_entry) -> SanctionedEntity:
        """Parse individual SDN entry."""
        try:
            # Basic info
            uid = sdn_entry.get('uid', '')
            
            # Get first/last name or entity name
            first_name = self._get_text(sdn_entry, 'firstName', '')
            last_name = self._get_text(sdn_entry, 'lastName', '')
            entity_name = self._get_text(sdn_entry, 'title', '')
            
            # Construct full name
            if first_name or last_name:
                name = f"{first_name} {last_name}".strip()
                entity_type = "Person"
            else:
                name = entity_name
                entity_type = "Entity"
            
            if not name:
                return None
            
            # Programs (sanctions lists)
            programs = []
            for program in sdn_entry.findall('.//program'):
                program_text = program.text
                if program_text:
                    programs.append(program_text.strip())
            
            # Addresses
            addresses = []
            for address in sdn_entry.findall('.//address'):
                addr_parts = []
                for field in ['address1', 'address2', 'city', 'stateOrProvince', 'country']:
                    value = self._get_text(address, field)
                    if value:
                        addr_parts.append(value)
                if addr_parts:
                    addresses.append(', '.join(addr_parts))
            
            # Aliases (AKAs)
            aliases = []
            for aka in sdn_entry.findall('.//aka'):
                aka_first = self._get_text(aka, 'firstName', '')
                aka_last = self._get_text(aka, 'lastName', '')
                aka_name = self._get_text(aka, 'title', '')
                
                if aka_first or aka_last:
                    alias = f"{aka_first} {aka_last}".strip()
                else:
                    alias = aka_name
                
                if alias and alias != name:
                    aliases.append(alias)
            
            # Dates of birth
            dates_of_birth = []
            for dob in sdn_entry.findall('.//dateOfBirth'):
                dob_text = dob.text
                if dob_text:
                    dates_of_birth.append(dob_text.strip())
            
            # Places of birth  
            places_of_birth = []
            for pob in sdn_entry.findall('.//placeOfBirth'):
                pob_text = pob.text
                if pob_text:
                    places_of_birth.append(pob_text.strip())
            
            # Nationalities
            nationalities = []
            for nat in sdn_entry.findall('.//nationality'):
                nat_text = nat.text
                if nat_text:
                    nationalities.append(nat_text.strip())
            
            # Remarks
            remarks = self._get_text(sdn_entry, 'remarks', '')
            
            return SanctionedEntity(
                uid=uid,
                name=name,
                entity_type=entity_type,
                programs=programs,
                addresses=addresses,
                aliases=aliases,
                dates_of_birth=dates_of_birth,
                places_of_birth=places_of_birth,
                nationalities=nationalities,
                remarks=remarks,
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse SDN entry {sdn_entry.get('uid', 'unknown')}: {e}")
            return None
    
    def _get_text(self, element, tag: str, default: str = '') -> str:
        """Safely get text from XML element."""
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else default
    
    def scrape_and_parse(self) -> List[SanctionedEntity]:
        """
        Main method: download and parse OFAC SDN list.
        
        Returns:
            List of sanctioned entities.
        """
        xml_content = self.download_sdn_list()
        entities = self.parse_entities(xml_content)
        return entities

# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scraper = OFACScraper()
    entities = scraper.scrape_and_parse()
    
    print(f"\n🎯 Successfully scraped {len(entities)} entities from OFAC!")
    
    # Show first few entities
    for i, entity in enumerate(entities[:3]):
        print(f"\n--- Entity {i+1} ---")
        print(f"Name: {entity.name}")
        print(f"Type: {entity.entity_type}")
        print(f"Programs: {', '.join(entity.programs)}")
        print(f"Aliases: {', '.join(entity.aliases[:2])}")
        if entity.addresses:
            print(f"Address: {entity.addresses[0]}")