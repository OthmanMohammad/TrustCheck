import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

@dataclass
class SanctionedEntity:
    """Represents a sanctioned entity from OFAC with all available data."""
    uid: str
    name: str
    entity_type: str  # "PERSON", "COMPANY", "VESSEL", "AIRCRAFT", "OTHER"
    sdn_type: Optional[str]  # Raw OFAC sdnType field
    programs: List[str]
    addresses: List[str]
    aliases: List[str]
    dates_of_birth: List[str]
    places_of_birth: List[str]
    nationalities: List[str]
    remarks: Optional[str]
    source: str = "OFAC"
    last_updated: datetime = None
    
    # Person-specific fields (only filled for persons)
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class OFACScraper:
    """
    Production-ready OFAC SDN scraper with correct entity classification.
    
    Features:
    - Correct entity type mapping using OFAC's sdnType field
    - Comprehensive data extraction (addresses, aliases, dates, etc.)
    - Namespace-aware XML parsing
    - Performance monitoring
    - Error handling and recovery
    - Progress reporting
    """
    
    SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    
    # Official OFAC entity type mapping
    ENTITY_TYPE_MAP = {
        'individual': 'PERSON',
        'entity': 'COMPANY', 
        'vessel': 'VESSEL',
        'aircraft': 'AIRCRAFT'
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrustCheck-Compliance-Platform/2.0',
            'Accept': 'application/xml, text/xml',
            'Accept-Encoding': 'gzip, deflate'
        })
        self.namespace = None
        
        # Statistics tracking
        self.stats = {
            'total_processed': 0,
            'total_parsed': 0,
            'parse_errors': 0,
            'persons': 0,
            'companies': 0,
            'vessels': 0,
            'aircraft': 0,
            'other': 0,
            'with_aliases': 0,
            'with_addresses': 0,
            'with_birth_dates': 0
        }
    
    def download_sdn_list(self) -> str:
        """Download the OFAC SDN XML file with error handling."""
        logger.info(f"📥 Downloading OFAC SDN from: {self.SDN_URL}")
        
        try:
            start_time = time.time()
            response = self.session.get(self.SDN_URL, timeout=120, stream=True)
            response.raise_for_status()
            
            # Get content
            content = response.text
            download_time = time.time() - start_time
            size_mb = len(content.encode('utf-8')) / (1024 * 1024)
            
            logger.info(f"✅ Downloaded {size_mb:.1f}MB in {download_time:.1f}s")
            
            # Basic validation
            if len(content) < 10000:
                raise ValueError("Downloaded content too small - likely an error page")
            
            if not content.strip().startswith('<?xml'):
                raise ValueError("Downloaded content is not XML")
            
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error downloading SDN: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error downloading SDN: {e}")
            raise
    
    def _detect_namespace(self, root) -> str:
        """Detect and store XML namespace."""
        if root.tag.startswith('{'):
            namespace = root.tag.split('}')[0] + '}'
            logger.info(f"🔍 Detected namespace: {namespace}")
        else:
            namespace = ''
            logger.info("🔍 No namespace detected")
        
        return namespace
    
    def _get_text(self, element, tag_name: str, default: str = '') -> str:
        """Safely extract text from XML element with namespace support."""
        try:
            if self.namespace:
                child = element.find(f'{self.namespace}{tag_name}')
            else:
                child = element.find(tag_name)
            
            if child is not None and child.text:
                return child.text.strip()
        except Exception:
            pass
        
        return default
    
    def _find_elements(self, element, tag_name: str):
        """Find child elements with namespace support."""
        try:
            if self.namespace:
                return element.findall(f'{self.namespace}{tag_name}')
            else:
                return element.findall(tag_name)
        except Exception:
            return []
    
    def _find_element(self, element, tag_name: str):
        """Find single child element with namespace support."""
        try:
            if self.namespace:
                return element.find(f'{self.namespace}{tag_name}')
            else:
                return element.find(tag_name)
        except Exception:
            return None
    
    def parse_entities(self, xml_content: str) -> List[SanctionedEntity]:
        """Parse XML content with comprehensive error handling."""
        logger.info("🔍 Parsing OFAC XML content...")
        
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            self.namespace = self._detect_namespace(root)
            
            # Find all SDN entries
            if self.namespace:
                sdn_entries = root.findall(f'.//{self.namespace}sdnEntry')
            else:
                sdn_entries = root.findall('.//sdnEntry')
            
            logger.info(f"📊 Found {len(sdn_entries):,} SDN entries in XML")
            
            if not sdn_entries:
                logger.error("❌ No SDN entries found! Check XML structure")
                # Save sample for debugging
                with open('debug_no_entries.xml', 'w', encoding='utf-8') as f:
                    f.write(xml_content[:5000])
                return []
            
            # Parse entities
            entities = []
            start_time = time.time()
            
            for i, entry in enumerate(sdn_entries):
                self.stats['total_processed'] += 1
                
                try:
                    entity = self._parse_sdn_entry(entry)
                    if entity:
                        entities.append(entity)
                        self.stats['total_parsed'] += 1
                        self._update_stats(entity)
                    
                    # Progress reporting
                    if (i + 1) % 2500 == 0:
                        elapsed = time.time() - start_time
                        rate = (i + 1) / elapsed
                        eta = (len(sdn_entries) - i - 1) / rate
                        logger.info(f"📈 Parsed {i + 1:,}/{len(sdn_entries):,} entries "
                                   f"({rate:.0f}/sec, ETA: {eta:.0f}s)")
                
                except Exception as e:
                    self.stats['parse_errors'] += 1
                    if self.stats['parse_errors'] <= 5:  # Only log first few errors
                        logger.warning(f"⚠️ Failed to parse entry {i}: {e}")
            
            parse_time = time.time() - start_time
            logger.info(f"✅ Parsed {len(entities):,} entities from {len(sdn_entries):,} entries "
                       f"in {parse_time:.1f}s ({len(entities)/parse_time:.0f}/sec)")
            
            return entities
            
        except ET.ParseError as e:
            logger.error(f"❌ XML parsing failed: {e}")
            # Save problematic XML
            with open('debug_parse_error.xml', 'w', encoding='utf-8') as f:
                f.write(xml_content[:10000])
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected parsing error: {e}")
            raise
    
    def _parse_sdn_entry(self, entry) -> Optional[SanctionedEntity]:
        """
        Parse individual SDN entry using OFFICIAL OFAC fields.
        
        KEY FIX: Uses <sdnType> for correct entity classification.
        """
        
        # Get UID (required)
        uid = self._get_text(entry, 'uid')
        if not uid:
            return None
        
        # FIXED: Use official OFAC sdnType field
        sdn_type = self._get_text(entry, 'sdnType', '').lower().strip()
        entity_type = self.ENTITY_TYPE_MAP.get(sdn_type, 'OTHER')
        
        # FIXED: Use lastName as primary name (OFAC standard)
        # Even company names are stored in lastName field
        last_name = self._get_text(entry, 'lastName')
        first_name = self._get_text(entry, 'firstName')
        title = self._get_text(entry, 'title')
        
        # Construct display name using OFAC conventions
        if last_name:
            if first_name and entity_type == 'PERSON':
                # Person: "First Last"
                display_name = f"{first_name} {last_name}".strip()
            else:
                # Company/Entity: just lastName (which contains full company name)
                display_name = last_name
        elif title:
            # Fallback to title field
            display_name = title
        else:
            # No name found - skip this entry
            return None
        
        # Extract all additional data
        try:
            programs = self._extract_programs(entry)
            addresses = self._extract_addresses(entry)
            aliases = self._extract_aliases(entry, display_name)
            dates_of_birth = self._extract_dates_of_birth(entry)
            places_of_birth = self._extract_places_of_birth(entry)
            nationalities = self._extract_nationalities(entry)
            remarks = self._get_text(entry, 'remarks')
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting data for UID {uid}: {e}")
            # Still create entity with basic info
            programs = addresses = aliases = dates_of_birth = []
            places_of_birth = nationalities = []
            remarks = None
        
        return SanctionedEntity(
            uid=uid,
            name=display_name,
            entity_type=entity_type,
            sdn_type=sdn_type or None,
            programs=programs,
            addresses=addresses,
            aliases=aliases,
            dates_of_birth=dates_of_birth,
            places_of_birth=places_of_birth,
            nationalities=nationalities,
            remarks=remarks,
            first_name=first_name if entity_type == 'PERSON' else None,
            last_name=last_name if entity_type == 'PERSON' else None,
            last_updated=datetime.utcnow()
        )
    
    def _update_stats(self, entity: SanctionedEntity):
        """Update parsing statistics."""
        # Count by type
        if entity.entity_type == 'PERSON':
            self.stats['persons'] += 1
        elif entity.entity_type == 'COMPANY':
            self.stats['companies'] += 1
        elif entity.entity_type == 'VESSEL':
            self.stats['vessels'] += 1
        elif entity.entity_type == 'AIRCRAFT':
            self.stats['aircraft'] += 1
        else:
            self.stats['other'] += 1
        
        # Count data richness
        if entity.aliases:
            self.stats['with_aliases'] += 1
        if entity.addresses:
            self.stats['with_addresses'] += 1
        if entity.dates_of_birth:
            self.stats['with_birth_dates'] += 1
    
    def _extract_programs(self, entry) -> List[str]:
        """Extract sanctions programs."""
        programs = []
        program_list = self._find_element(entry, 'programList')
        
        if program_list is not None:
            for program in self._find_elements(program_list, 'program'):
                text = self._get_text(program, '', '')
                if not text:
                    text = program.text or ''
                text = text.strip()
                if text:
                    programs.append(text)
        
        return programs
    
    def _extract_addresses(self, entry) -> List[str]:
        """Extract and format addresses."""
        addresses = []
        address_list = self._find_element(entry, 'addressList')
        
        if address_list is not None:
            for addr in self._find_elements(address_list, 'address'):
                addr_parts = []
                
                # Extract all address components
                for field in ['address1', 'address2', 'address3', 
                             'city', 'stateOrProvince', 'postalCode', 'country']:
                    value = self._get_text(addr, field)
                    if value:
                        addr_parts.append(value)
                
                if addr_parts:
                    full_address = ', '.join(addr_parts)
                    addresses.append(full_address)
        
        return addresses
    
    def _extract_aliases(self, entry, main_name: str) -> List[str]:
        """Extract aliases/AKAs."""
        aliases = []
        aka_list = self._find_element(entry, 'akaList')
        
        if aka_list is not None:
            for aka in self._find_elements(aka_list, 'aka'):
                # Try different alias name fields
                aka_first = self._get_text(aka, 'firstName')
                aka_last = self._get_text(aka, 'lastName') 
                aka_title = self._get_text(aka, 'title')
                
                if aka_first or aka_last:
                    alias = f"{aka_first} {aka_last}".strip()
                else:
                    alias = aka_title.strip()
                
                # Only add if different from main name and not empty
                if alias and alias != main_name and len(alias) > 1:
                    aliases.append(alias)
        
        return aliases
    
    def _extract_dates_of_birth(self, entry) -> List[str]:
        """Extract dates of birth."""
        dates = []
        
        # Try structured dateOfBirthList first
        dob_list = self._find_element(entry, 'dateOfBirthList')
        if dob_list is not None:
            for dob in self._find_elements(dob_list, 'dateOfBirthItem'):
                date_value = (self._get_text(dob, 'dateOfBirth') or 
                             self._get_text(dob, 'date') or 
                             (dob.text or '').strip())
                if date_value:
                    dates.append(date_value)
        
        # Try direct dateOfBirth elements (legacy format)
        if not dates:
            for dob in self._find_elements(entry, 'dateOfBirth'):
                date_value = (dob.text or '').strip()
                if date_value:
                    dates.append(date_value)
        
        return dates
    
    def _extract_places_of_birth(self, entry) -> List[str]:
        """Extract places of birth."""
        places = []
        
        # Try structured placeOfBirthList
        pob_list = self._find_element(entry, 'placeOfBirthList')
        if pob_list is not None:
            for pob in self._find_elements(pob_list, 'placeOfBirthItem'):
                place_value = (self._get_text(pob, 'placeOfBirth') or
                              self._get_text(pob, 'place') or
                              (pob.text or '').strip())
                if place_value:
                    places.append(place_value)
        
        # Try direct elements
        if not places:
            for pob in self._find_elements(entry, 'placeOfBirth'):
                place_value = (pob.text or '').strip()
                if place_value:
                    places.append(place_value)
        
        return places
    
    def _extract_nationalities(self, entry) -> List[str]:
        """Extract nationalities."""
        nationalities = []
        
        # Try structured nationalityList
        nat_list = self._find_element(entry, 'nationalityList')
        if nat_list is not None:
            for nat in self._find_elements(nat_list, 'nationalityItem'):
                nat_value = (self._get_text(nat, 'nationality') or
                           self._get_text(nat, 'country') or
                           (nat.text or '').strip())
                if nat_value:
                    nationalities.append(nat_value)
        
        # Try direct elements
        if not nationalities:
            for nat in self._find_elements(entry, 'nationality'):
                nat_value = (nat.text or '').strip()
                if nat_value:
                    nationalities.append(nat_value)
        
        return nationalities
    
    def scrape_and_parse(self) -> List[SanctionedEntity]:
        """
        Main scraping method with comprehensive logging and error handling.
        """
        total_start = time.time()
        
        try:
            logger.info("🕷️ Starting OFAC SDN scraping (FIXED VERSION)")
            
            # Reset stats
            self.stats = {k: 0 for k in self.stats}
            
            # Download
            download_start = time.time()
            xml_content = self.download_sdn_list()
            download_time = time.time() - download_start
            
            # Parse
            parse_start = time.time()
            entities = self.parse_entities(xml_content)
            parse_time = time.time() - parse_start
            
            total_time = time.time() - total_start
            
            # Log comprehensive results
            if entities:
                logger.info("✅ OFAC scraping completed successfully!")
                logger.info(f"   ⏱️ Total time: {total_time:.1f}s (download: {download_time:.1f}s, parse: {parse_time:.1f}s)")
                logger.info(f"   📊 Entities parsed: {len(entities):,} / {self.stats['total_processed']:,}")
                
                if self.stats['parse_errors'] > 0:
                    logger.warning(f"   ⚠️ Parse errors: {self.stats['parse_errors']:,}")
                
                # Entity type breakdown
                logger.info(f"   👤 Persons: {self.stats['persons']:,}")
                logger.info(f"   🏢 Companies: {self.stats['companies']:,}")
                logger.info(f"   🚢 Vessels: {self.stats['vessels']:,}")
                logger.info(f"   ✈️ Aircraft: {self.stats['aircraft']:,}")
                logger.info(f"   📋 Other: {self.stats['other']:,}")
                
                # Data quality metrics
                logger.info(f"   🏷️ With aliases: {self.stats['with_aliases']:,} ({self.stats['with_aliases']/len(entities)*100:.1f}%)")
                logger.info(f"   📍 With addresses: {self.stats['with_addresses']:,} ({self.stats['with_addresses']/len(entities)*100:.1f}%)")
                logger.info(f"   📅 With birth dates: {self.stats['with_birth_dates']:,} ({self.stats['with_birth_dates']/len(entities)*100:.1f}%)")
                
                # Show sample entities by type
                logger.info("   🎯 Sample entities by type:")
                shown_by_type = {}
                for entity in entities[:50]:  # Check first 50
                    if entity.entity_type not in shown_by_type and len(shown_by_type) < 4:
                        shown_by_type[entity.entity_type] = entity
                        logger.info(f"     • {entity.name} ({entity.entity_type}) - Programs: {entity.programs[:2]}")
                
            else:
                logger.error("❌ No entities parsed - check logs for errors!")
                
            return entities
            
        except Exception as e:
            logger.error(f"❌ OFAC scraping failed after {time.time() - total_start:.1f}s: {e}")
            raise

# Test and CLI functionality
def main():
    """Test the scraper directly."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing FIXED OFAC Scraper")
    print("=" * 60)
    
    scraper = OFACScraper()
    entities = scraper.scrape_and_parse()
    
    print(f"\n🎯 FINAL RESULTS:")
    print(f"   📊 Total entities: {len(entities):,}")
    
    if entities:
        # Show examples of each type
        examples = {}
        for entity in entities:
            if entity.entity_type not in examples:
                examples[entity.entity_type] = []
            if len(examples[entity.entity_type]) < 3:
                examples[entity.entity_type].append(entity)
        
        print(f"\n📋 Examples by entity type:")
        for entity_type, entity_list in examples.items():
            print(f"\n   {entity_type}:")
            for i, entity in enumerate(entity_list, 1):
                print(f"     {i}. {entity.name}")
                if entity.aliases:
                    print(f"        Aliases: {entity.aliases[:2]}")
                if entity.addresses:
                    print(f"        Address: {entity.addresses[0][:80]}...")
                if entity.programs:
                    print(f"        Programs: {entity.programs}")
    
    print(f"\n{'='*60}")
    print(f"✅ Test completed!")
    
    return entities

if __name__ == "__main__":
    main()