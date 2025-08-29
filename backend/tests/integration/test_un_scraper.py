"""
Tests for UN Consolidated Sanctions List Scraper.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import xml.etree.ElementTree as ET

from src.scrapers.international.un.scraper import UNScraper, UNSanctionedEntityData
from src.scrapers.base.scraper import ScrapingResult

# Sample UN XML data for testing
SAMPLE_UN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST>
    <INDIVIDUALS>
        <INDIVIDUAL>
            <DATAID>12345</DATAID>
            <FIRST_NAME>John</FIRST_NAME>
            <SECOND_NAME>Michael</SECOND_NAME>
            <THIRD_NAME>Smith</THIRD_NAME>
            <UN_LIST_TYPE>ISIL (Da'esh) and Al-Qaida</UN_LIST_TYPE>
            <LISTED_ON>2020-01-15</LISTED_ON>
            <COMMENTS1>Test individual for sanctions</COMMENTS1>
            <INDIVIDUAL_ALIAS>
                <QUALITY>Good</QUALITY>
                <ALIAS_NAME>Johnny Smith</ALIAS_NAME>
            </INDIVIDUAL_ALIAS>
            <INDIVIDUAL_ADDRESS>
                <STREET>123 Test Street</STREET>
                <CITY>Test City</CITY>
                <COUNTRY>Test Country</COUNTRY>
            </INDIVIDUAL_ADDRESS>
            <INDIVIDUAL_DATE_OF_BIRTH>
                <DATE>1980-05-15</DATE>
            </INDIVIDUAL_DATE_OF_BIRTH>
            <INDIVIDUAL_PLACE_OF_BIRTH>
                <CITY>Birth City</CITY>
                <COUNTRY>Birth Country</COUNTRY>
            </INDIVIDUAL_PLACE_OF_BIRTH>
            <NATIONALITY>
                <VALUE>Test Nationality</VALUE>
            </NATIONALITY>
        </INDIVIDUAL>
    </INDIVIDUALS>
    <ENTITIES>
        <ENTITY>
            <DATAID>67890</DATAID>
            <FIRST_NAME>Test Organization Ltd</FIRST_NAME>
            <UN_LIST_TYPE>Taliban</UN_LIST_TYPE>
            <LISTED_ON>2021-06-20</LISTED_ON>
            <COMMENTS1>Test entity for sanctions</COMMENTS1>
            <ENTITY_ALIAS>
                <ALIAS_NAME>Test Org</ALIAS_NAME>
            </ENTITY_ALIAS>
            <ENTITY_ADDRESS>
                <STREET>456 Business Avenue</STREET>
                <CITY>Business City</CITY>
                <COUNTRY>Business Country</COUNTRY>
            </ENTITY_ADDRESS>
        </ENTITY>
    </ENTITIES>
</CONSOLIDATED_LIST>
"""

@pytest.fixture
def un_scraper():
    """Create UN scraper instance for testing."""
    return UNScraper()

@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for testing."""
    mock_response = AsyncMock()
    mock_response.text = AsyncMock(return_value=SAMPLE_UN_XML)
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    return mock_session

class TestUNScraper:
    """Test suite for UN scraper."""
    
    @pytest.mark.asyncio
    async def test_download_data(self, un_scraper, mock_aiohttp_session):
        """Test downloading UN XML data."""
        with patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
            result = await un_scraper.download_data()
            
            assert result == SAMPLE_UN_XML
            mock_aiohttp_session.get.assert_called_once_with(
                un_scraper.UN_CONSOLIDATED_URL,
                headers=un_scraper.headers,
                timeout=pytest.Any()
            )
    
    def test_parse_individual_entry(self, un_scraper):
        """Test parsing individual entry from UN XML."""
        root = ET.fromstring(SAMPLE_UN_XML)
        individual_entry = root.find('.//INDIVIDUALS/INDIVIDUAL')
        
        result = un_scraper._parse_individual_entry(individual_entry)
        
        assert result is not None
        assert result.uid == "UN-IND-12345"
        assert result.name == "John Michael Smith"
        assert result.entity_type == "PERSON"
        assert result.first_name == "John"
        assert result.second_name == "Michael"
        assert result.third_name == "Smith"
        assert "ISIL (Da'esh) and Al-Qaida" in result.programs
        assert "Johnny Smith" in result.aliases
        assert len(result.addresses) == 1
        assert "123 Test Street" in result.addresses[0]
        assert "1980-05-15" in result.dates_of_birth
        assert len(result.places_of_birth) == 1
        assert "Test Nationality" in result.nationalities
        assert result.listed_on == "2020-01-15"
    
    def test_parse_entity_entry(self, un_scraper):
        """Test parsing entity (organization) entry from UN XML."""
        root = ET.fromstring(SAMPLE_UN_XML)
        entity_entry = root.find('.//ENTITIES/ENTITY')
        
        result = un_scraper._parse_entity_entry(entity_entry)
        
        assert result is not None
        assert result.uid == "UN-ENT-67890"
        assert result.name == "Test Organization Ltd"
        assert result.entity_type == "COMPANY"
        assert "Taliban" in result.programs
        assert "Test Org" in result.aliases
        assert len(result.addresses) == 1
        assert "456 Business Avenue" in result.addresses[0]
        assert result.listed_on == "2021-06-20"
    
    def test_parse_un_entities_internal(self, un_scraper):
        """Test parsing complete UN XML."""
        entities = un_scraper._parse_un_entities_internal(SAMPLE_UN_XML)
        
        assert len(entities) == 2
        
        # Check individual
        individual = next(e for e in entities if e.entity_type == "PERSON")
        assert individual.name == "John Michael Smith"
        
        # Check entity
        entity = next(e for e in entities if e.entity_type == "COMPANY")
        assert entity.name == "Test Organization Ltd"
        
        # Check statistics
        assert un_scraper.stats['individuals'] == 1
        assert un_scraper.stats['entities'] == 1
        assert un_scraper.stats['total_parsed'] == 2
    
    @pytest.mark.asyncio
    async def test_parse_entities(self, un_scraper):
        """Test async parse_entities method."""
        result = await un_scraper.parse_entities(SAMPLE_UN_XML)
        
        assert len(result) == 2
        assert all(isinstance(item, dict) for item in result)
        
        # Check that dictionaries have required fields
        for entity_dict in result:
            assert 'uid' in entity_dict
            assert 'name' in entity_dict
            assert 'entity_type' in entity_dict
            assert 'programs' in entity_dict
            assert 'aliases' in entity_dict
    
    @pytest.mark.asyncio
    async def test_store_entities(self, un_scraper):
        """Test storing entities in database."""
        entity_dicts = [
            {
                'uid': 'UN-TEST-001',
                'name': 'Test Entity',
                'entity_type': 'PERSON',
                'programs': ['Test Program'],
                'aliases': [],
                'addresses': [],
                'dates_of_birth': [],
                'places_of_birth': [],
                'nationalities': [],
                'remarks': None
            }
        ]
        
        with patch('src.scrapers.international.un.scraper.db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.get_session.return_value.__aenter__.return_value = mock_session
            
            await un_scraper.store_entities(entity_dicts)
            
            # Verify delete was called for existing UN data
            mock_session.execute.assert_called()
            
            # Verify new entity was added
            mock_session.add.assert_called()
            
            # Verify commit was called
            mock_session.commit.assert_called()
    
    def test_extract_programs(self, un_scraper):
        """Test extracting sanctions programs."""
        xml_str = """
        <INDIVIDUAL>
            <UN_LIST_TYPE>ISIL (Da'esh) and Al-Qaida</UN_LIST_TYPE>
            <COMMITTEE>1267 Committee</COMMITTEE>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        programs = un_scraper._extract_programs(entry)
        
        assert len(programs) == 2
        assert "ISIL (Da'esh) and Al-Qaida" in programs
        assert "1267 Committee" in programs
    
    def test_extract_addresses(self, un_scraper):
        """Test extracting addresses."""
        xml_str = """
        <INDIVIDUAL>
            <INDIVIDUAL_ADDRESS>
                <STREET>123 Main St</STREET>
                <CITY>New York</CITY>
                <STATE_PROVINCE>NY</STATE_PROVINCE>
                <ZIP_CODE>10001</ZIP_CODE>
                <COUNTRY>United States</COUNTRY>
            </INDIVIDUAL_ADDRESS>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        addresses = un_scraper._extract_addresses(entry)
        
        assert len(addresses) == 1
        assert "123 Main St" in addresses[0]
        assert "New York" in addresses[0]
        assert "United States" in addresses[0]
    
    def test_update_stats(self, un_scraper):
        """Test statistics tracking."""
        entity = UNSanctionedEntityData(
            uid="TEST-001",
            name="Test Name",
            entity_type="PERSON",
            programs=["Test Program"],
            addresses=["Test Address"],
            aliases=["Test Alias"],
            dates_of_birth=["1980-01-01"],
            places_of_birth=[],
            nationalities=[],
            designations=["Test Title"],
            remarks=None
        )
        
        un_scraper._update_stats(entity)
        
        assert un_scraper.stats['with_aliases'] == 1
        assert un_scraper.stats['with_addresses'] == 1
        assert un_scraper.stats['with_birth_dates'] == 1
        assert un_scraper.stats['with_designations'] == 1
    
    @pytest.mark.asyncio
    async def test_scrape_and_store_integration(self, un_scraper):
        """Test complete scraping workflow (mocked)."""
        with patch.object(un_scraper.download_manager, 'download_content') as mock_download:
            with patch.object(un_scraper.download_manager, 'should_skip_processing') as mock_skip:
                with patch.object(un_scraper, '_get_current_entities') as mock_get_entities:
                    with patch.object(un_scraper, 'store_entities') as mock_store:
                        # Setup mocks
                        mock_download.return_value = AsyncMock(
                            success=True,
                            content=SAMPLE_UN_XML,
                            content_hash='test_hash',
                            size_bytes=1000,
                            download_time_ms=100
                        )
                        mock_skip.return_value = False
                        mock_get_entities.return_value = []
                        mock_store.return_value = None
                        
                        # Execute
                        result = await un_scraper.scrape_and_store()
                        
                        # Verify
                        assert isinstance(result, ScrapingResult)
                        assert result.source == "un"
                        assert result.status in ["SUCCESS", "SKIPPED"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])