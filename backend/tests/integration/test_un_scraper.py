"""
Integration tests for UN Sanctions List Scraper - FIXED VERSION
Tests the complete UN scraper with proper async mocking.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from datetime import datetime
import xml.etree.ElementTree as ET

from src.scrapers.international.un.scraper import UNScraper, UNSanctionedEntityData
from src.scrapers.base.scraper import ScrapingResult


class TestUNScraper:
    """Comprehensive tests for UN scraper with proper async mocking."""
    
    @pytest.fixture
    def un_scraper(self):
        """Create UN scraper instance."""
        return UNScraper()
    
    @pytest.fixture
    def sample_un_xml(self):
        """Sample UN XML data for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <DATAID>12345</DATAID>
                    <FIRST_NAME>John</FIRST_NAME>
                    <SECOND_NAME>Michael</SECOND_NAME>
                    <THIRD_NAME>Smith</THIRD_NAME>
                    <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
                    <LISTED_ON>2020-01-15</LISTED_ON>
                    <COMMENTS1>Test individual</COMMENTS1>
                    <INDIVIDUAL_ALIAS>
                        <ALIAS_NAME>Johnny Smith</ALIAS_NAME>
                        <QUALITY>Good</QUALITY>
                    </INDIVIDUAL_ALIAS>
                    <INDIVIDUAL_ADDRESS>
                        <STREET>123 Test St</STREET>
                        <CITY>New York</CITY>
                        <COUNTRY>United States</COUNTRY>
                    </INDIVIDUAL_ADDRESS>
                    <INDIVIDUAL_DATE_OF_BIRTH>
                        <DATE>1980-01-01</DATE>
                    </INDIVIDUAL_DATE_OF_BIRTH>
                    <INDIVIDUAL_PLACE_OF_BIRTH>
                        <CITY>London</CITY>
                        <COUNTRY>United Kingdom</COUNTRY>
                    </INDIVIDUAL_PLACE_OF_BIRTH>
                    <NATIONALITY>
                        <VALUE>United Kingdom</VALUE>
                    </NATIONALITY>
                </INDIVIDUAL>
            </INDIVIDUALS>
            <ENTITIES>
                <ENTITY>
                    <DATAID>67890</DATAID>
                    <FIRST_NAME>Test Organization Ltd</FIRST_NAME>
                    <UN_LIST_TYPE>Taliban</UN_LIST_TYPE>
                    <LISTED_ON>2021-05-20</LISTED_ON>
                    <ENTITY_ALIAS>
                        <ALIAS_NAME>Test Org</ALIAS_NAME>
                    </ENTITY_ALIAS>
                    <ENTITY_ADDRESS>
                        <STREET>456 Business Ave</STREET>
                        <CITY>Dubai</CITY>
                        <COUNTRY>United Arab Emirates</COUNTRY>
                    </ENTITY_ADDRESS>
                </ENTITY>
            </ENTITIES>
        </CONSOLIDATED_LIST>"""
    
    @pytest.fixture
    def mock_aiohttp_session(self):
        """Create properly mocked aiohttp session for async context manager."""
        # Create mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<xml>test</xml>")
        mock_response.raise_for_status = Mock()
        
        # Make response work as async context manager
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock session
        mock_session = AsyncMock()
        
        # Make session.get return an object that works as async context manager
        mock_get = AsyncMock(return_value=mock_response)
        mock_session.get = Mock(return_value=mock_response)  # Return the response directly
        
        # Make session work as async context manager
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        return mock_session
    
    # ======================== DOWNLOAD TESTS ========================
    
    @pytest.mark.asyncio
    async def test_download_data(self, un_scraper, mock_aiohttp_session):
        """Test downloading UN XML data - FIXED."""
        # Set up the response text
        mock_aiohttp_session.get.return_value.text = AsyncMock(
            return_value="<CONSOLIDATED_LIST><test>data</test></CONSOLIDATED_LIST>"
        )
        
        # Patch aiohttp.ClientSession to return our mock
        with patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
            # Call download_data
            result = await un_scraper.download_data()
            
            # Verify result
            assert result == "<CONSOLIDATED_LIST><test>data</test></CONSOLIDATED_LIST>"
            
            # Verify session.get was called with correct URL
            mock_aiohttp_session.get.assert_called_once()
            call_args = mock_aiohttp_session.get.call_args
            assert call_args[0][0] == un_scraper.UN_CONSOLIDATED_URL
    
    @pytest.mark.asyncio
    async def test_download_data_error_handling(self, un_scraper):
        """Test error handling in download_data - FIXED."""
        # Create a mock response that raises an exception
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = Exception("Network error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create a mock session that returns the response as a context manager
        mock_session = AsyncMock()
        # THIS IS THE FIX: Don't use .return_value, just return the mock_response directly
        mock_session.get = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Should raise the exception
            with pytest.raises(Exception) as exc_info:
                await un_scraper.download_data()
            
            assert "Network error" in str(exc_info.value)
    
    # ======================== PARSING TESTS ========================
    
    def test_parse_individual_entry(self, un_scraper, sample_un_xml):
        """Test parsing individual person entry."""
        root = ET.fromstring(sample_un_xml)
        individual = root.find('.//INDIVIDUAL')
        
        result = un_scraper._parse_individual_entry(individual)
        
        assert result is not None
        assert result.uid == "UN-IND-12345"
        assert result.name == "John Michael Smith"
        assert result.entity_type == "PERSON"
        assert result.programs == ["Al-Qaida"]
        assert "Johnny Smith" in result.aliases
        assert len(result.addresses) == 1
        assert "123 Test St" in result.addresses[0]
        assert result.dates_of_birth == ["1980-01-01"]
        assert len(result.places_of_birth) == 1
        assert result.nationalities == ["United Kingdom"]
    
    def test_parse_entity_entry(self, un_scraper, sample_un_xml):
        """Test parsing entity/organization entry."""
        root = ET.fromstring(sample_un_xml)
        entity = root.find('.//ENTITY')
        
        result = un_scraper._parse_entity_entry(entity)
        
        assert result is not None
        assert result.uid == "UN-ENT-67890"
        assert result.name == "Test Organization Ltd"
        assert result.entity_type == "COMPANY"
        assert result.programs == ["Taliban"]
        assert "Test Org" in result.aliases
        assert len(result.addresses) == 1
        assert "456 Business Ave" in result.addresses[0]
    
    def test_parse_un_entities_internal(self, un_scraper, sample_un_xml):
        """Test complete XML parsing."""
        entities = un_scraper._parse_un_entities_internal(sample_un_xml)
        
        assert len(entities) == 2
        
        # Check individual
        individual = next(e for e in entities if e.entity_type == "PERSON")
        assert individual.name == "John Michael Smith"
        
        # Check entity
        entity = next(e for e in entities if e.entity_type == "COMPANY")
        assert entity.name == "Test Organization Ltd"
    
    @pytest.mark.asyncio
    async def test_parse_entities(self, un_scraper, sample_un_xml):
        """Test async parse_entities method."""
        result = await un_scraper.parse_entities(sample_un_xml)
        
        assert len(result) == 2
        assert all(isinstance(e, dict) for e in result)
        
        # Check that entities are converted to dictionaries
        individual = next(e for e in result if e['entity_type'] == "PERSON")
        assert individual['name'] == "John Michael Smith"
        assert individual['uid'] == "UN-IND-12345"
    
    # ======================== STORAGE TESTS ========================
    
    @pytest.mark.asyncio
    async def test_store_entities(self, un_scraper):
        """Test storing entities in database."""
        entities = [
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
        
        with patch('src.infrastructure.database.connection.db_manager.get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_get_session.return_value = mock_session
            
            await un_scraper.store_entities(entities)
            
            # Verify database operations were called
            assert mock_session.execute.called
            assert mock_session.commit.called
    
    # ======================== DATA EXTRACTION TESTS ========================
    
    def test_extract_programs(self, un_scraper):
        """Test extracting sanctions programs."""
        xml_str = """
        <INDIVIDUAL>
            <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
            <COMMITTEE>Security Council</COMMITTEE>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        programs = un_scraper._extract_programs(entry)
        
        assert "Al-Qaida" in programs
        assert "Security Council" in programs
    
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
        assert "10001" in addresses[0]
    
    def test_update_stats(self, un_scraper):
        """Test statistics update."""
        entity = UNSanctionedEntityData(
            uid="TEST-001",
            name="Test",
            entity_type="PERSON",
            un_list_type="TEST",
            programs=[],
            addresses=["Address 1"],
            aliases=["Alias 1"],
            dates_of_birth=["1980-01-01"],
            places_of_birth=[],
            nationalities=[],
            designations=["Title"],
            remarks=None
        )
        
        un_scraper._update_stats(entity)
        
        assert un_scraper.stats['with_aliases'] == 1
        assert un_scraper.stats['with_addresses'] == 1
        assert un_scraper.stats['with_birth_dates'] == 1
        assert un_scraper.stats['with_designations'] == 1
    
    # ======================== INTEGRATION TESTS ========================
    
    @pytest.mark.asyncio
    async def test_scrape_and_store_integration(self, un_scraper, sample_un_xml):
        """Test complete scraping workflow."""
        # Mock download manager
        with patch.object(un_scraper.download_manager, 'download_content') as mock_download:
            mock_download.return_value = AsyncMock(
                success=True,
                content=sample_un_xml,
                content_hash='test_hash',
                size_bytes=len(sample_un_xml),
                download_time_ms=100
            )
            
            # Mock should_skip_processing to return False
            with patch.object(un_scraper.download_manager, 'should_skip_processing') as mock_skip:
                mock_skip.return_value = False
                
                # Mock database operations
                with patch('src.infrastructure.database.connection.db_manager.get_session') as mock_get_session:
                    mock_session = AsyncMock()
                    mock_session.execute = AsyncMock()
                    mock_session.commit = AsyncMock()
                    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session.__aexit__ = AsyncMock(return_value=None)
                    
                    mock_get_session.return_value = mock_session
                    
                    # Mock other required methods
                    with patch.object(un_scraper, '_get_current_entities', return_value=[]):
                        with patch.object(un_scraper, '_get_last_content_hash', return_value=''):
                            # Execute scraping
                            result = await un_scraper.scrape_and_store()
                            
                            # Verify result
                            assert result.status == "SUCCESS"
                            assert result.source == "un"
                            assert result.entities_processed == 2
    
    # ======================== FIELD EXTRACTION TESTS ========================
    
    def test_extract_individual_aliases(self, un_scraper):
        """Test extracting aliases for individuals."""
        xml_str = """
        <INDIVIDUAL>
            <INDIVIDUAL_ALIAS>
                <ALIAS_NAME>John Doe</ALIAS_NAME>
                <QUALITY>Good</QUALITY>
            </INDIVIDUAL_ALIAS>
            <INDIVIDUAL_ALIAS>
                <ALIAS_NAME>Johnny D</ALIAS_NAME>
                <QUALITY>Low</QUALITY>
            </INDIVIDUAL_ALIAS>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        aliases = un_scraper._extract_individual_aliases(entry)
        
        assert len(aliases) == 2
        assert "John Doe" in aliases
        assert "Johnny D" in aliases
    
    def test_extract_entity_aliases(self, un_scraper):
        """Test extracting aliases for entities."""
        xml_str = """
        <ENTITY>
            <ENTITY_ALIAS>
                <ALIAS_NAME>Company ABC</ALIAS_NAME>
            </ENTITY_ALIAS>
            <ENTITY_ALIAS>
                <ALIAS_NAME>ABC Corp</ALIAS_NAME>
            </ENTITY_ALIAS>
        </ENTITY>
        """
        entry = ET.fromstring(xml_str)
        
        aliases = un_scraper._extract_entity_aliases(entry)
        
        assert len(aliases) == 2
        assert "Company ABC" in aliases
        assert "ABC Corp" in aliases
    
    def test_extract_dates_of_birth(self, un_scraper):
        """Test extracting dates of birth."""
        xml_str = """
        <INDIVIDUAL>
            <INDIVIDUAL_DATE_OF_BIRTH>
                <DATE>1980-01-01</DATE>
            </INDIVIDUAL_DATE_OF_BIRTH>
            <INDIVIDUAL_DATE_OF_BIRTH>
                <YEAR>1980</YEAR>
            </INDIVIDUAL_DATE_OF_BIRTH>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        dates = un_scraper._extract_dates_of_birth(entry)
        
        assert len(dates) == 2
        assert "1980-01-01" in dates
        assert "1980" in dates
    
    def test_extract_places_of_birth(self, un_scraper):
        """Test extracting places of birth."""
        xml_str = """
        <INDIVIDUAL>
            <INDIVIDUAL_PLACE_OF_BIRTH>
                <CITY>London</CITY>
                <STATE_PROVINCE>England</STATE_PROVINCE>
                <COUNTRY>United Kingdom</COUNTRY>
            </INDIVIDUAL_PLACE_OF_BIRTH>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        places = un_scraper._extract_places_of_birth(entry)
        
        assert len(places) == 1
        assert "London, England, United Kingdom" in places
    
    def test_extract_nationalities(self, un_scraper):
        """Test extracting nationalities."""
        xml_str = """
        <INDIVIDUAL>
            <NATIONALITY>
                <VALUE>United Kingdom</VALUE>
            </NATIONALITY>
            <NATIONALITY>
                <VALUE>France</VALUE>
            </NATIONALITY>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        nationalities = un_scraper._extract_nationalities(entry)
        
        assert len(nationalities) == 2
        assert "United Kingdom" in nationalities
        assert "France" in nationalities
    
    def test_extract_designations(self, un_scraper):
        """Test extracting designations/titles."""
        xml_str = """
        <INDIVIDUAL>
            <DESIGNATION>
                <VALUE>Finance Minister</VALUE>
            </DESIGNATION>
            <DESIGNATION>
                <VALUE>CEO</VALUE>
            </DESIGNATION>
        </INDIVIDUAL>
        """
        entry = ET.fromstring(xml_str)
        
        designations = un_scraper._extract_designations(entry)
        
        assert len(designations) == 2
        assert "Finance Minister" in designations
        assert "CEO" in designations
    
    def test_get_text(self, un_scraper):
        """Test safe text extraction."""
        xml_str = """
        <TEST>
            <FIELD1>Value1</FIELD1>
            <FIELD2></FIELD2>
            <FIELD3>  Trimmed  </FIELD3>
        </TEST>
        """
        element = ET.fromstring(xml_str)
        
        assert un_scraper._get_text(element, 'FIELD1') == 'Value1'
        assert un_scraper._get_text(element, 'FIELD2') == ''
        assert un_scraper._get_text(element, 'FIELD3') == 'Trimmed'
        assert un_scraper._get_text(element, 'MISSING', 'default') == 'default'
    
    def test_un_entity_type_mapping(self, un_scraper):
        """Test entity type mapping."""
        assert un_scraper.ENTITY_TYPE_MAP['individual'] == 'PERSON'
        assert un_scraper.ENTITY_TYPE_MAP['entity'] == 'COMPANY'
        assert un_scraper.ENTITY_TYPE_MAP['vessel'] == 'VESSEL'
        assert un_scraper.ENTITY_TYPE_MAP['aircraft'] == 'AIRCRAFT'
    
    # ======================== ERROR HANDLING TESTS ========================
    
    def test_parse_empty_xml(self, un_scraper):
        """Test parsing empty XML."""
        empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS></INDIVIDUALS>
            <ENTITIES></ENTITIES>
        </CONSOLIDATED_LIST>"""
        
        entities = un_scraper._parse_un_entities_internal(empty_xml)
        
        assert entities == []
        assert un_scraper.stats['total_parsed'] == 0
    
    def test_parse_malformed_entry(self, un_scraper):
        """Test parsing malformed entry (missing required fields)."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <!-- Missing DATAID -->
                    <FIRST_NAME>John</FIRST_NAME>
                </INDIVIDUAL>
            </INDIVIDUALS>
        </CONSOLIDATED_LIST>"""
        
        entities = un_scraper._parse_un_entities_internal(xml_str)
        
        # Should skip the malformed entry
        assert len(entities) == 0