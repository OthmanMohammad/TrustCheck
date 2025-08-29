"""
UN Consolidated Sanctions List Scraper with Change Detection - FULLY ASYNC VERSION

Scrapes the United Nations Security Council Consolidated Sanctions List.
"""

import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import time
import hashlib
from sqlalchemy import select, delete

from src.scrapers.base.change_aware_scraper import ChangeAwareScraper
from src.scrapers.base.scraper import ScrapingResult
from src.scrapers.registry import scraper_registry, ScraperMetadata, Region, ScraperTier
from src.infrastructure.database.connection import db_manager
from src.infrastructure.database.models import SanctionedEntity

# ======================== DATA MODELS ========================

@dataclass
class UNSanctionedEntityData:
    """Represents a sanctioned entity from UN with all available data."""
    uid: str  # UN reference number (DATAID)
    name: str
    entity_type: str  # "PERSON", "COMPANY", "OTHER"
    un_list_type: Optional[str]  # Original UN list type
    programs: List[str]  # Sanctions regimes/committees
    addresses: List[str]
    aliases: List[str]
    dates_of_birth: List[str]
    places_of_birth: List[str]
    nationalities: List[str]
    designations: List[str]  # Professional titles/positions
    remarks: Optional[str]
    source: str = "UN"
    last_updated: datetime = None
    
    # Person-specific fields
    first_name: Optional[str] = None
    second_name: Optional[str] = None
    third_name: Optional[str] = None
    fourth_name: Optional[str] = None
    
    # Additional UN-specific fields
    listed_on: Optional[str] = None  # Date when entity was listed
    reference_number: Optional[str] = None  # Additional reference
    comments: Optional[str] = None  # UN-specific comments

# ======================== ASYNC UN SCRAPER ========================

class UNScraper(ChangeAwareScraper):
    """
    UN Consolidated Sanctions List scraper with AUTOMATIC change detection - FULLY ASYNC.
    
    This scraper:
    1. Downloads UN Consolidated XML data
    2. Automatically calculates content hash
    3. Skips processing if content unchanged
    4. Compares with previous data to detect changes
    5. Stores changes with risk classification
    6. Sends notifications for critical changes
    
    UN XML Structure:
    - INDIVIDUALS: Contains individual persons
    - ENTITIES: Contains organizations/companies
    - Uses different field naming than OFAC
    """
    
    UN_CONSOLIDATED_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    
    # UN entity type mapping
    ENTITY_TYPE_MAP = {
        'individual': 'PERSON',
        'entity': 'COMPANY',
        'vessel': 'VESSEL',
        'aircraft': 'AIRCRAFT'
    }
    
    def __init__(self):
        # Initialize with source URL for change detection
        super().__init__("un", self.UN_CONSOLIDATED_URL)
        
        # HTTP headers
        self.headers = {
            'User-Agent': 'TrustCheck-Compliance-Platform/2.0',
            'Accept': 'application/xml, text/xml',
            'Accept-Encoding': 'gzip, deflate'
        }
        
        # Statistics tracking
        self.stats = {
            'total_processed': 0,
            'total_parsed': 0,
            'parse_errors': 0,
            'individuals': 0,
            'entities': 0,
            'with_aliases': 0,
            'with_addresses': 0,
            'with_birth_dates': 0,
            'with_designations': 0
        }
    
    # ======================== CHANGE-AWARE SCRAPER INTERFACE (ASYNC) ========================
    
    async def download_data(self) -> str:
        """
        Download UN XML data - ASYNC.
        
        Note: This method is not used in ChangeAwareScraper,
        but we implement it for compatibility.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.UN_CONSOLIDATED_URL,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response.raise_for_status()
                return await response.text()
    
    async def parse_entities(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parse UN XML into entity dictionaries - ASYNC.
        
        Returns List[Dict] for ChangeAwareScraper interface.
        """
        # Parse XML using internal logic (synchronous)
        parsed_entities = self._parse_un_entities_internal(xml_content)
        
        # Convert to dictionaries for change detection
        entity_dicts = []
        for entity_data in parsed_entities:
            entity_dict = {
                'uid': entity_data.uid,
                'name': entity_data.name,
                'entity_type': entity_data.entity_type,
                'programs': entity_data.programs,
                'aliases': entity_data.aliases,
                'addresses': entity_data.addresses,
                'dates_of_birth': entity_data.dates_of_birth,
                'places_of_birth': entity_data.places_of_birth,
                'nationalities': entity_data.nationalities,
                'remarks': entity_data.remarks
            }
            entity_dicts.append(entity_dict)
        
        return entity_dicts
    
    async def store_entities(self, entity_dicts: List[Dict[str, Any]]) -> None:
        """
        Store entity dictionaries in database - ASYNC.
        
        Args:
            entity_dicts: List of entity dictionaries from parse_entities()
        """
        self.logger.info(f"Storing {len(entity_dicts)} UN entities in database...")
        
        async with db_manager.get_session() as session:
            try:
                # Clear existing UN data
                await session.execute(
                    delete(SanctionedEntity).where(
                        SanctionedEntity.source == "UN"
                    )
                )
                
                self.logger.info(f"Deleted existing UN entities")
                
                # Insert new entities
                stored_count = 0
                for entity_dict in entity_dicts:
                    # Generate content hash for this entity
                    entity_content = f"{entity_dict['name']}{entity_dict['entity_type']}{entity_dict.get('programs', [])}"
                    content_hash = hashlib.sha256(entity_content.encode('utf-8')).hexdigest()
                    
                    db_entity = SanctionedEntity(
                        uid=entity_dict['uid'],
                        name=entity_dict['name'],
                        entity_type=entity_dict['entity_type'],
                        source="UN",
                        programs=entity_dict.get('programs'),
                        aliases=entity_dict.get('aliases'),
                        addresses=entity_dict.get('addresses'),
                        dates_of_birth=entity_dict.get('dates_of_birth'),
                        places_of_birth=entity_dict.get('places_of_birth'),
                        nationalities=entity_dict.get('nationalities'),
                        remarks=entity_dict.get('remarks'),
                        content_hash=content_hash,
                        last_seen=datetime.utcnow()
                    )
                    session.add(db_entity)
                    stored_count += 1
                    
                    # Commit in batches for performance
                    if stored_count % 1000 == 0:
                        await session.commit()
                        self.logger.info(f"Stored {stored_count}/{len(entity_dicts)} entities...")
                
                # Final commit
                await session.commit()
                
                self.logger.info(f"Successfully stored {stored_count} UN entities in database")
                
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to store entities: {e}")
                raise
    
    # ======================== INTERNAL PARSING METHODS (SYNCHRONOUS) ========================
    
    def _parse_un_entities_internal(self, xml_content: str) -> List[UNSanctionedEntityData]:
        """
        Internal method that parses XML content.
        Returns UNSanctionedEntityData objects for internal use.
        
        UN XML has different structure than OFAC:
        - INDIVIDUALS section for persons
        - ENTITIES section for organizations
        - Different field names and structure
        """
        self.logger.info("Parsing UN XML content...")
        
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            entities = []
            
            # Parse INDIVIDUALS section
            individuals_section = root.find('.//INDIVIDUALS')
            if individuals_section is not None:
                individual_entries = individuals_section.findall('.//INDIVIDUAL')
                self.logger.info(f"Found {len(individual_entries):,} individual entries")
                
                for entry in individual_entries:
                    try:
                        entity = self._parse_individual_entry(entry)
                        if entity:
                            entities.append(entity)
                            self.stats['individuals'] += 1
                            self.stats['total_parsed'] += 1
                            self._update_stats(entity)
                    except Exception as e:
                        self.stats['parse_errors'] += 1
                        if self.stats['parse_errors'] <= 5:
                            self.logger.warning(f"Failed to parse individual: {e}")
            
            # Parse ENTITIES section (organizations)
            entities_section = root.find('.//ENTITIES')
            if entities_section is not None:
                entity_entries = entities_section.findall('.//ENTITY')
                self.logger.info(f"Found {len(entity_entries):,} entity entries")
                
                for entry in entity_entries:
                    try:
                        entity = self._parse_entity_entry(entry)
                        if entity:
                            entities.append(entity)
                            self.stats['entities'] += 1
                            self.stats['total_parsed'] += 1
                            self._update_stats(entity)
                    except Exception as e:
                        self.stats['parse_errors'] += 1
                        if self.stats['parse_errors'] <= 5:
                            self.logger.warning(f"Failed to parse entity: {e}")
            
            self.logger.info(
                f"Parsed {len(entities):,} entities "
                f"({self.stats['individuals']} individuals, {self.stats['entities']} entities)"
            )
            
            return entities
            
        except ET.ParseError as e:
            self.logger.error(f"XML parsing failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected parsing error: {e}")
            raise
    
    # ======================== INDIVIDUAL PARSING ========================
    
    def _parse_individual_entry(self, entry) -> Optional[UNSanctionedEntityData]:
        """Parse individual person entry from UN XML."""
        
        # Get unique identifier (DATAID is the UN reference)
        dataid = self._get_text(entry, 'DATAID')
        if not dataid:
            return None
        
        uid = f"UN-IND-{dataid}"
        
        # Parse name components
        first_name = self._get_text(entry, 'FIRST_NAME')
        second_name = self._get_text(entry, 'SECOND_NAME')
        third_name = self._get_text(entry, 'THIRD_NAME')
        fourth_name = self._get_text(entry, 'FOURTH_NAME')
        
        # Construct full name (UN format)
        name_parts = [n for n in [first_name, second_name, third_name, fourth_name] if n]
        full_name = ' '.join(name_parts) if name_parts else self._get_text(entry, 'NAME_ORIGINAL_SCRIPT', 'Unknown')
        
        # Parse sanctions programs/committees
        programs = self._extract_programs(entry)
        
        # Parse aliases
        aliases = self._extract_individual_aliases(entry)
        
        # Parse addresses
        addresses = self._extract_addresses(entry)
        
        # Parse dates of birth
        dates_of_birth = self._extract_dates_of_birth(entry)
        
        # Parse places of birth
        places_of_birth = self._extract_places_of_birth(entry)
        
        # Parse nationalities
        nationalities = self._extract_nationalities(entry)
        
        # Parse designations (titles/positions)
        designations = self._extract_designations(entry)
        
        # Get additional information
        comments = self._get_text(entry, 'COMMENTS1')
        listed_on = self._get_text(entry, 'LISTED_ON')
        reference_number = self._get_text(entry, 'REFERENCE_NUMBER')
        
        return UNSanctionedEntityData(
            uid=uid,
            name=full_name,
            entity_type='PERSON',
            un_list_type='INDIVIDUAL',
            programs=programs,
            addresses=addresses,
            aliases=aliases,
            dates_of_birth=dates_of_birth,
            places_of_birth=places_of_birth,
            nationalities=nationalities,
            designations=designations,
            remarks=comments,
            first_name=first_name,
            second_name=second_name,
            third_name=third_name,
            fourth_name=fourth_name,
            listed_on=listed_on,
            reference_number=reference_number,
            comments=comments,
            last_updated=datetime.utcnow()
        )
    
    # ======================== ENTITY (ORGANIZATION) PARSING ========================
    
    def _parse_entity_entry(self, entry) -> Optional[UNSanctionedEntityData]:
        """Parse entity (organization) entry from UN XML."""
        
        # Get unique identifier
        dataid = self._get_text(entry, 'DATAID')
        if not dataid:
            return None
        
        uid = f"UN-ENT-{dataid}"
        
        # Get entity name
        name = self._get_text(entry, 'FIRST_NAME')  # UN uses FIRST_NAME for entity names
        if not name:
            name = self._get_text(entry, 'NAME_ORIGINAL_SCRIPT', 'Unknown')
        
        # Parse sanctions programs/committees
        programs = self._extract_programs(entry)
        
        # Parse aliases
        aliases = self._extract_entity_aliases(entry)
        
        # Parse addresses
        addresses = self._extract_addresses(entry)
        
        # Get additional information
        comments = self._get_text(entry, 'COMMENTS1')
        listed_on = self._get_text(entry, 'LISTED_ON')
        reference_number = self._get_text(entry, 'REFERENCE_NUMBER')
        
        return UNSanctionedEntityData(
            uid=uid,
            name=name,
            entity_type='COMPANY',
            un_list_type='ENTITY',
            programs=programs,
            addresses=addresses,
            aliases=aliases,
            dates_of_birth=[],  # Not applicable for entities
            places_of_birth=[],  # Not applicable for entities
            nationalities=[],  # Organizations don't have nationalities in UN format
            designations=[],
            remarks=comments,
            listed_on=listed_on,
            reference_number=reference_number,
            comments=comments,
            last_updated=datetime.utcnow()
        )
    
    # ======================== DATA EXTRACTION HELPERS ========================
    
    def _get_text(self, element, tag_name: str, default: str = '') -> str:
        """Safely extract text from XML element."""
        try:
            child = element.find(tag_name)
            if child is not None and child.text:
                return child.text.strip()
        except Exception:
            pass
        return default
    
    def _extract_programs(self, entry) -> List[str]:
        """Extract sanctions programs/committees from UN entry."""
        programs = []
        
        # UN uses UN_LIST_TYPE for the sanctions regime
        list_type = self._get_text(entry, 'UN_LIST_TYPE')
        if list_type:
            programs.append(list_type)
        
        # Also check for committee information
        committee = self._get_text(entry, 'COMMITTEE')
        if committee and committee not in programs:
            programs.append(committee)
        
        return programs
    
    def _extract_individual_aliases(self, entry) -> List[str]:
        """Extract aliases for individuals."""
        aliases = []
        
        # Look for INDIVIDUAL_ALIAS nodes
        alias_nodes = entry.findall('.//INDIVIDUAL_ALIAS')
        for alias_node in alias_nodes:
            alias_name = self._get_text(alias_node, 'ALIAS_NAME')
            if alias_name:
                aliases.append(alias_name)
            
            # Also check quality of alias (good/low)
            quality = self._get_text(alias_node, 'QUALITY')
            # We include all aliases regardless of quality
        
        return aliases
    
    def _extract_entity_aliases(self, entry) -> List[str]:
        """Extract aliases for entities/organizations."""
        aliases = []
        
        # Look for ENTITY_ALIAS nodes
        alias_nodes = entry.findall('.//ENTITY_ALIAS')
        for alias_node in alias_nodes:
            alias_name = self._get_text(alias_node, 'ALIAS_NAME')
            if alias_name:
                aliases.append(alias_name)
        
        return aliases
    
    def _extract_addresses(self, entry) -> List[str]:
        """Extract addresses from UN entry."""
        addresses = []
        
        # Look for ADDRESS nodes (both INDIVIDUAL_ADDRESS and ENTITY_ADDRESS)
        address_nodes = entry.findall('.//INDIVIDUAL_ADDRESS') + entry.findall('.//ENTITY_ADDRESS')
        
        for addr_node in address_nodes:
            addr_parts = []
            
            # UN address fields
            street = self._get_text(addr_node, 'STREET')
            city = self._get_text(addr_node, 'CITY')
            state_province = self._get_text(addr_node, 'STATE_PROVINCE')
            postal_code = self._get_text(addr_node, 'ZIP_CODE')
            country = self._get_text(addr_node, 'COUNTRY')
            
            # Build address string
            for part in [street, city, state_province, postal_code, country]:
                if part:
                    addr_parts.append(part)
            
            if addr_parts:
                full_address = ', '.join(addr_parts)
                addresses.append(full_address)
        
        return addresses
    
    def _extract_dates_of_birth(self, entry) -> List[str]:
        """Extract dates of birth from individual entry."""
        dates = []
        
        # Look for INDIVIDUAL_DATE_OF_BIRTH nodes
        dob_nodes = entry.findall('.//INDIVIDUAL_DATE_OF_BIRTH')
        for dob_node in dob_nodes:
            date = self._get_text(dob_node, 'DATE')
            year = self._get_text(dob_node, 'YEAR')
            
            if date:
                dates.append(date)
            elif year:
                dates.append(year)  # Sometimes only year is available
        
        return dates
    
    def _extract_places_of_birth(self, entry) -> List[str]:
        """Extract places of birth from individual entry."""
        places = []
        
        # Look for INDIVIDUAL_PLACE_OF_BIRTH nodes
        pob_nodes = entry.findall('.//INDIVIDUAL_PLACE_OF_BIRTH')
        for pob_node in pob_nodes:
            city = self._get_text(pob_node, 'CITY')
            state_province = self._get_text(pob_node, 'STATE_PROVINCE')
            country = self._get_text(pob_node, 'COUNTRY')
            
            place_parts = [p for p in [city, state_province, country] if p]
            if place_parts:
                places.append(', '.join(place_parts))
        
        return places
    
    def _extract_nationalities(self, entry) -> List[str]:
        """Extract nationalities from individual entry."""
        nationalities = []
        
        # Look for NATIONALITY nodes
        nat_nodes = entry.findall('.//NATIONALITY')
        for nat_node in nat_nodes:
            country = self._get_text(nat_node, 'VALUE')
            if country:
                nationalities.append(country)
        
        return nationalities
    
    def _extract_designations(self, entry) -> List[str]:
        """Extract designations/titles from entry."""
        designations = []
        
        # Look for DESIGNATION nodes
        desig_nodes = entry.findall('.//DESIGNATION')
        for desig_node in desig_nodes:
            designation = self._get_text(desig_node, 'VALUE')
            if designation:
                designations.append(designation)
        
        return designations
    
    def _update_stats(self, entity: UNSanctionedEntityData):
        """Update parsing statistics."""
        if entity.aliases:
            self.stats['with_aliases'] += 1
        if entity.addresses:
            self.stats['with_addresses'] += 1
        if entity.dates_of_birth:
            self.stats['with_birth_dates'] += 1
        if entity.designations:
            self.stats['with_designations'] += 1

# ======================== REGISTRY REGISTRATION ========================

# Register the UN scraper in the global registry
scraper_registry.register(
    UNScraper,
    ScraperMetadata(
        name="un",
        region=Region.INTERNATIONAL,
        tier=ScraperTier.TIER1,
        update_frequency="24 hours",
        entity_count=13000,  # Approximate
        complexity="MEDIUM",
        data_format="XML",
        requires_auth=False
    )
)