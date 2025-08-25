"""
OFAC SDN List Scraper

1. Uses official OFAC <sdnType> field for correct entity classification
2. Uses <lastName> as primary name (OFAC standard - even for companies)
3. Extracts all data fields properly (aliases, addresses, dates, etc.)
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import time
from sqlalchemy.orm import Session

from src.scrapers.base.scraper import BaseScraper, ScrapingResult
from src.scrapers.registry import scraper_registry, ScraperMetadata, Region, ScraperTier
from src.database.connection import db_manager
from src.database.models import SanctionedEntity

# ======================== DATA MODELS ========================

@dataclass
class SanctionedEntityData:
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

# ======================== MAIN SCRAPER CLASS ========================

class OFACScraper(BaseScraper):
    """
    Production-ready OFAC SDN scraper with REAL database storage.
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
        super().__init__("US_OFAC")
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
    
    # ======================== BASE SCRAPER INTERFACE ========================
    
    def download_data(self) -> str:
        """Download OFAC SDN XML data."""
        return self.download_sdn_list()
    
    def parse_entities(self, xml_content: str) -> List[SanctionedEntityData]:
        """Parse OFAC XML into entities."""
        return self.parse_ofac_entities(xml_content)
    
    def store_entities(self, entities: List[SanctionedEntityData]) -> None:
        """FIXED: Actually store OFAC entities in database."""
        self.logger.info(f"Storing {len(entities)} OFAC entities in database...")
        
        with db_manager.get_session() as db:
            try:
                # Clear existing OFAC data
                deleted_count = db.query(SanctionedEntity).filter(
                    SanctionedEntity.source == "OFAC"
                ).delete()
                
                self.logger.info(f"Deleted {deleted_count} existing OFAC entities")
                
                # Insert new entities
                stored_count = 0
                for entity_data in entities:
                    db_entity = SanctionedEntity(
                        uid=entity_data.uid,
                        name=entity_data.name,
                        entity_type=entity_data.entity_type,
                        source=entity_data.source,
                        programs=entity_data.programs,
                        aliases=entity_data.aliases,
                        addresses=entity_data.addresses,
                        dates_of_birth=entity_data.dates_of_birth,
                        places_of_birth=entity_data.places_of_birth,
                        nationalities=entity_data.nationalities,
                        remarks=entity_data.remarks,
                        last_seen=entity_data.last_updated
                    )
                    db.add(db_entity)
                    stored_count += 1
                    
                    # Commit in batches for better performance
                    if stored_count % 1000 == 0:
                        db.commit()
                        self.logger.info(f"Stored {stored_count}/{len(entities)} entities...")
                
                # Final commit
                db.commit()
                
                self.logger.info(f"✅ Successfully stored {stored_count} OFAC entities in database")
                
                # Show sample entities
                for entity in entities[:3]:
                    self.logger.info(f"  - {entity.name} ({entity.entity_type})")
                    
            except Exception as e:
                db.rollback()
                self.logger.error(f"Failed to store entities: {e}")
                raise
    
    # ======================== DOWNLOAD METHODS ========================
    
    def download_sdn_list(self) -> str:
        """Download the OFAC SDN XML file with error handling."""
        self.logger.info(f"Downloading OFAC SDN from: {self.SDN_URL}")
        
        try:
            start_time = time.time()
            response = self.session.get(self.SDN_URL, timeout=120, stream=True)
            response.raise_for_status()
            
            # Get content
            content = response.text
            download_time = time.time() - start_time
            size_mb = len(content.encode('utf-8')) / (1024 * 1024)
            
            self.logger.info(f"Downloaded {size_mb:.1f}MB in {download_time:.1f}s")
            
            # Basic validation
            if len(content) < 10000:
                raise ValueError("Downloaded content too small - likely an error page")
            
            if not content.strip().startswith('<?xml'):
                raise ValueError("Downloaded content is not XML")
            
            return content
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading SDN: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error downloading SDN: {e}")
            raise
    
    # ======================== PARSING METHODS ========================
    
    def _detect_namespace(self, root) -> str:
        """Detect and store XML namespace."""
        if root.tag.startswith('{'):
            namespace = root.tag.split('}')[0] + '}'
            self.logger.info(f"Detected namespace: {namespace}")
        else:
            namespace = ''
            self.logger.info("No namespace detected")
        
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
    
    def parse_ofac_entities(self, xml_content: str) -> List[SanctionedEntityData]:
        """Parse XML content with comprehensive error handling."""
        self.logger.info("Parsing OFAC XML content...")
        
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            self.namespace = self._detect_namespace(root)
            
            # Find all SDN entries
            if self.namespace:
                sdn_entries = root.findall(f'.//{self.namespace}sdnEntry')
            else:
                sdn_entries = root.findall('.//sdnEntry')
            
            self.logger.info(f"Found {len(sdn_entries):,} SDN entries in XML")
            
            if not sdn_entries:
                self.logger.error("No SDN entries found! Check XML structure")
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
                        self.logger.info(f"Parsed {i + 1:,}/{len(sdn_entries):,} entries "
                                       f"({rate:.0f}/sec, ETA: {eta:.0f}s)")
                
                except Exception as e:
                    self.stats['parse_errors'] += 1
                    if self.stats['parse_errors'] <= 5:
                        self.logger.warning(f"Failed to parse entry {i}: {e}")
            
            parse_time = time.time() - start_time
            self.logger.info(f"Parsed {len(entities):,} entities from {len(sdn_entries):,} entries "
                           f"in {parse_time:.1f}s ({len(entities)/parse_time:.0f}/sec)")
            
            return entities
            
        except ET.ParseError as e:
            self.logger.error(f"XML parsing failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected parsing error: {e}")
            raise
    
    def _parse_sdn_entry(self, entry) -> Optional[SanctionedEntityData]:
        """Parse individual SDN entry using OFFICIAL OFAC fields."""
        
        # Get UID (required)
        uid = self._get_text(entry, 'uid')
        if not uid:
            return None
        
        # Use official OFAC sdnType field
        sdn_type = self._get_text(entry, 'sdnType', '').lower().strip()
        entity_type = self.ENTITY_TYPE_MAP.get(sdn_type, 'OTHER')
        
        # Use lastName as primary name (OFAC standard)
        last_name = self._get_text(entry, 'lastName')
        first_name = self._get_text(entry, 'firstName')
        title = self._get_text(entry, 'title')
        
        # Construct display name using OFAC conventions
        if last_name:
            if first_name and entity_type == 'PERSON':
                display_name = f"{first_name} {last_name}".strip()
            else:
                display_name = last_name
        elif title:
            display_name = title
        else:
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
            self.logger.warning(f"Error extracting data for UID {uid}: {e}")
            programs = addresses = aliases = dates_of_birth = []
            places_of_birth = nationalities = []
            remarks = None
        
        return SanctionedEntityData(
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
    
    # ======================== DATA EXTRACTION HELPERS ========================
    
    def _update_stats(self, entity: SanctionedEntityData):
        """Update parsing statistics."""
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
                aka_first = self._get_text(aka, 'firstName')
                aka_last = self._get_text(aka, 'lastName') 
                aka_title = self._get_text(aka, 'title')
                
                if aka_first or aka_last:
                    alias = f"{aka_first} {aka_last}".strip()
                else:
                    alias = aka_title.strip()
                
                if alias and alias != main_name and len(alias) > 1:
                    aliases.append(alias)
        
        return aliases
    
    def _extract_dates_of_birth(self, entry) -> List[str]:
        """Extract dates of birth."""
        dates = []
        
        dob_list = self._find_element(entry, 'dateOfBirthList')
        if dob_list is not None:
            for dob in self._find_elements(dob_list, 'dateOfBirthItem'):
                date_value = (self._get_text(dob, 'dateOfBirth') or 
                             self._get_text(dob, 'date') or 
                             (dob.text or '').strip())
                if date_value:
                    dates.append(date_value)
        
        if not dates:
            for dob in self._find_elements(entry, 'dateOfBirth'):
                date_value = (dob.text or '').strip()
                if date_value:
                    dates.append(date_value)
        
        return dates
    
    def _extract_places_of_birth(self, entry) -> List[str]:
        """Extract places of birth."""
        places = []
        
        pob_list = self._find_element(entry, 'placeOfBirthList')
        if pob_list is not None:
            for pob in self._find_elements(pob_list, 'placeOfBirthItem'):
                place_value = (self._get_text(pob, 'placeOfBirth') or
                              self._get_text(pob, 'place') or
                              (pob.text or '').strip())
                if place_value:
                    places.append(place_value)
        
        if not places:
            for pob in self._find_elements(entry, 'placeOfBirth'):
                place_value = (pob.text or '').strip()
                if place_value:
                    places.append(place_value)
        
        return places
    
    def _extract_nationalities(self, entry) -> List[str]:
        """Extract nationalities."""
        nationalities = []
        
        nat_list = self._find_element(entry, 'nationalityList')
        if nat_list is not None:
            for nat in self._find_elements(nat_list, 'nationalityItem'):
                nat_value = (self._get_text(nat, 'nationality') or
                           self._get_text(nat, 'country') or
                           (nat.text or '').strip())
                if nat_value:
                    nationalities.append(nat_value)
        
        if not nationalities:
            for nat in self._find_elements(entry, 'nationality'):
                nat_value = (nat.text or '').strip()
                if nat_value:
                    nationalities.append(nat_value)
        
        return nationalities

# ======================== REGISTRY REGISTRATION ========================

# Register the OFAC scraper in the global registry
scraper_registry.register(
    OFACScraper,
    ScraperMetadata(
        name="us_ofac",
        region=Region.US,
        tier=ScraperTier.TIER1,
        update_frequency="6 hours",
        entity_count=8000,
        complexity="MEDIUM",
        data_format="XML",
        requires_auth=False
    )
)