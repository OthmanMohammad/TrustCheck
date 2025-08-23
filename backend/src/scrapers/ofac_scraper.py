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
    entity_type: str  # "PERSON", "COMPANY", etc.
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
    """Namespace-aware OFAC SDN list scraper."""
    
    SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrustCheck-Compliance-Platform/1.0'
        })
        self.namespace = None  # Will be detected from XML
    
    def download_sdn_list(self) -> str:
        """Download the OFAC SDN XML file."""
        logger.info(f"Downloading OFAC SDN list from {self.SDN_URL}")
        
        try:
            response = self.session.get(self.SDN_URL, timeout=120)
            response.raise_for_status()
            
            logger.info(f"Successfully downloaded SDN list ({len(response.content):,} bytes)")
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Failed to download SDN list: {e}")
            raise
    
    def _detect_namespace(self, root) -> str:
        """Detect XML namespace from root element."""
        if root.tag.startswith('{'):
            namespace = root.tag.split('}')[0] + '}'
            logger.info(f"Detected XML namespace: {namespace}")
            return namespace
        else:
            logger.info("No XML namespace detected")
            return ''
    
    def _get_text(self, element, tag_name: str, default: str = '') -> str:
        """Get text from element, handling namespace."""
        if self.namespace:
            child = element.find(f'{self.namespace}{tag_name}')
        else:
            child = element.find(tag_name)
        
        if child is not None and child.text:
            return child.text.strip()
        return default
    
    def _find_elements(self, element, tag_name: str):
        """Find child elements, handling namespace."""
        if self.namespace:
            return element.findall(f'{self.namespace}{tag_name}')
        else:
            return element.findall(tag_name)
    
    def parse_entities(self, xml_content: str) -> List[SanctionedEntity]:
        """Parse XML content with namespace support."""
        logger.info("Parsing OFAC XML content with namespace support...")
        
        try:
            root = ET.fromstring(xml_content)
            
            # Detect and store namespace
            self.namespace = self._detect_namespace(root)
            
            # Find SDN entries with namespace
            if self.namespace:
                sdn_entries = root.findall(f'.//{self.namespace}sdnEntry')
            else:
                sdn_entries = root.findall('.//sdnEntry')
            
            logger.info(f"Found {len(sdn_entries)} SDN entries in XML")
            
            if len(sdn_entries) == 0:
                logger.error("No SDN entries found! XML structure may have changed.")
                return []
            
            entities = []
            
            for i, entry in enumerate(sdn_entries):
                try:
                    entity = self._parse_sdn_entry(entry)
                    if entity:
                        entities.append(entity)
                        
                        # Log progress
                        if (i + 1) % 1000 == 0:
                            logger.info(f"Parsed {i + 1}/{len(sdn_entries)} entries...")
                            
                except Exception as e:
                    logger.warning(f"Failed to parse entry {i}: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(entities)} entities from {len(sdn_entries)} entries")
            return entities
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise
    
    def _parse_sdn_entry(self, entry) -> SanctionedEntity:
        """Parse individual SDN entry with namespace support."""
        
        # Get UID
        uid = self._get_text(entry, 'uid')
        if not uid:
            return None
        
        # Get name components
        first_name = self._get_text(entry, 'firstName')
        last_name = self._get_text(entry, 'lastName')
        title = self._get_text(entry, 'title')
        
        # Construct name and determine type
        if first_name or last_name:
            name = f"{first_name} {last_name}".strip()
            entity_type = "PERSON"
        elif title:
            name = title.strip()
            # Determine if it's a company or other entity
            company_indicators = ['corp', 'inc', 'ltd', 'llc', 'bank', 'company', 'enterprises']
            if any(indicator in name.lower() for indicator in company_indicators):
                entity_type = "COMPANY"
            else:
                entity_type = "OTHER"
        else:
            return None  # Skip if no name
        
        # Get programs
        programs = []
        program_list = entry.find(f'{self.namespace}programList') if self.namespace else entry.find('programList')
        if program_list is not None:
            for program in self._find_elements(program_list, 'program'):
                if program.text:
                    programs.append(program.text.strip())
        
        # Get addresses
        addresses = self._extract_addresses(entry)
        
        # Get aliases
        aliases = self._extract_aliases(entry, name)
        
        # Get dates of birth
        dates_of_birth = []
        for dob in self._find_elements(entry, 'dateOfBirth'):
            if dob.text:
                dates_of_birth.append(dob.text.strip())
        
        # Get places of birth
        places_of_birth = []
        for pob in self._find_elements(entry, 'placeOfBirth'):
            if pob.text:
                places_of_birth.append(pob.text.strip())
        
        # Get nationalities
        nationalities = []
        for nat in self._find_elements(entry, 'nationality'):
            if nat.text:
                nationalities.append(nat.text.strip())
        
        # Get remarks
        remarks = self._get_text(entry, 'remarks')
        
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
    
    def _extract_addresses(self, entry) -> List[str]:
        """Extract addresses with namespace support."""
        addresses = []
        
        for addr in self._find_elements(entry, 'address'):
            addr_parts = []
            
            # Common address fields
            addr_fields = ['address1', 'address2', 'city', 'stateOrProvince', 'postalCode', 'country']
            for field in addr_fields:
                value = self._get_text(addr, field)
                if value:
                    addr_parts.append(value)
            
            if addr_parts:
                addresses.append(', '.join(addr_parts))
        
        return addresses
    
    def _extract_aliases(self, entry, main_name: str) -> List[str]:
        """Extract aliases with namespace support."""
        aliases = []
        
        for aka in self._find_elements(entry, 'aka'):
            aka_first = self._get_text(aka, 'firstName')
            aka_last = self._get_text(aka, 'lastName')
            aka_title = self._get_text(aka, 'title')
            
            if aka_first or aka_last:
                alias = f"{aka_first} {aka_last}".strip()
            else:
                alias = aka_title.strip()
            
            # Only add if different from main name
            if alias and alias != main_name:
                aliases.append(alias)
        
        return aliases
    
    def scrape_and_parse(self) -> List[SanctionedEntity]:
        """Main method with detailed progress logging."""
        
        try:
            logger.info("🕷️ Starting OFAC SDN scraping...")
            
            # Download
            start_time = datetime.now()
            xml_content = self.download_sdn_list()
            download_time = (datetime.now() - start_time).total_seconds()
            
            # Parse
            parse_start = datetime.now()
            entities = self.parse_entities(xml_content)
            parse_time = (datetime.now() - parse_start).total_seconds()
            
            # Results
            total_time = download_time + parse_time
            
            if entities:
                logger.info(f"✅ OFAC scraping completed successfully!")
                logger.info(f"   📊 Total entities: {len(entities):,}")
                logger.info(f"   ⏱️ Download time: {download_time:.1f}s")
                logger.info(f"   ⏱️ Parse time: {parse_time:.1f}s")
                logger.info(f"   ⏱️ Total time: {total_time:.1f}s")
                
                # Count by type
                person_count = len([e for e in entities if e.entity_type == "PERSON"])
                company_count = len([e for e in entities if e.entity_type == "COMPANY"])
                other_count = len([e for e in entities if e.entity_type == "OTHER"])
                
                logger.info(f"   👤 Persons: {person_count:,}")
                logger.info(f"   🏢 Companies: {company_count:,}")
                logger.info(f"   📋 Other entities: {other_count:,}")
                
                # Show sample entities
                logger.info("   🎯 Sample entities:")
                for i, entity in enumerate(entities[:3]):
                    logger.info(f"     {i+1}. {entity.name} ({entity.entity_type}) - {entity.programs}")
                    
            else:
                logger.error("❌ No entities were parsed!")
                
            return entities
            
        except Exception as e:
            logger.error(f"❌ OFAC scraping failed: {e}")
            raise

# Test function
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    scraper = OFACScraper()
    entities = scraper.scrape_and_parse()
    
    print(f"\n🎯 FINAL RESULTS:")
    print(f"   📊 Entities scraped: {len(entities):,}")
    
    if entities:
        print(f"\n📋 First 3 entities:")
        for i, entity in enumerate(entities[:3]):
            print(f"   {i+1}. {entity.name}")
            print(f"      Type: {entity.entity_type}")
            print(f"      Programs: {entity.programs}")
            print(f"      UID: {entity.uid}")
            print()
    else:
        print("❌ No entities found - check logs for errors")