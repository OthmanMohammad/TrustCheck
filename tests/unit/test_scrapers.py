"""
TrustCheck Scraper Tests.

Unit tests for the sanctions list scrapers.
"""

import pytest

from trustcheck.domain import DataSource, EntityType
from trustcheck.scrapers.base import BaseScraper, RawEntity, ScrapeResult
from trustcheck.scrapers.ofac import OFACScraper
from trustcheck.scrapers.un import UNScraper
from trustcheck.scrapers.eu import EUScraper
from trustcheck.scrapers.uk import UKScraper


class TestRawEntity:
    """Tests for the RawEntity dataclass."""

    def test_basic_entity(self):
        """Test basic entity creation."""
        entity = RawEntity(
            source_uid="123",
            primary_name="John Smith",
            entity_type=EntityType.INDIVIDUAL,
        )

        assert entity.source_uid == "123"
        assert entity.primary_name == "John Smith"
        assert entity.entity_type == EntityType.INDIVIDUAL
        assert entity.names == []
        assert entity.addresses == []
        assert entity.identifiers == []
        assert entity.programs == []

    def test_entity_with_all_fields(self):
        """Test entity with all fields populated."""
        entity = RawEntity(
            source_uid="456",
            primary_name="Acme Corporation",
            entity_type=EntityType.ORGANIZATION,
            names=[{"value": "Acme Corp", "type": "ALIAS"}],
            addresses=[{"country": "US", "city": "New York"}],
            identifiers=[{"type": "TAX_ID", "value": "12-3456789"}],
            programs=["SDGT", "IEEPA"],
            date_of_birth="1980-01-01",
            place_of_birth="New York, USA",
            nationality="US",
            remarks="Test remarks",
            raw_data={"key": "value"},
        )

        assert entity.source_uid == "456"
        assert len(entity.names) == 1
        assert len(entity.addresses) == 1
        assert len(entity.identifiers) == 1
        assert len(entity.programs) == 2
        assert entity.date_of_birth == "1980-01-01"
        assert entity.nationality == "US"


class TestScrapeResult:
    """Tests for the ScrapeResult dataclass."""

    def test_basic_result(self):
        """Test basic scrape result."""
        result = ScrapeResult(source=DataSource.OFAC_SDN, success=True)

        assert result.source == DataSource.OFAC_SDN
        assert result.success is True
        assert result.entities == []
        assert result.error_message is None

    def test_failed_result(self):
        """Test failed scrape result."""
        result = ScrapeResult(
            source=DataSource.UN,
            success=False,
            error_message="Connection timeout",
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"


class TestBaseScraper:
    """Tests for BaseScraper utility methods."""

    def test_hash_content(self):
        """Test content hashing."""
        scraper = OFACScraper()
        content = b"test content"

        hash1 = scraper._hash_content(content)
        hash2 = scraper._hash_content(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_hash_different_content(self):
        """Test that different content produces different hashes."""
        scraper = OFACScraper()

        hash1 = scraper._hash_content(b"content 1")
        hash2 = scraper._hash_content(b"content 2")

        assert hash1 != hash2

    def test_detect_entity_type_individual(self):
        """Test individual type detection."""
        scraper = OFACScraper()

        assert scraper._detect_entity_type("Individual") == EntityType.INDIVIDUAL
        assert scraper._detect_entity_type("PERSON") == EntityType.INDIVIDUAL
        assert scraper._detect_entity_type("human") == EntityType.INDIVIDUAL

    def test_detect_entity_type_organization(self):
        """Test organization type detection."""
        scraper = OFACScraper()

        assert scraper._detect_entity_type("Entity") == EntityType.ORGANIZATION
        assert scraper._detect_entity_type("ORGANIZATION") == EntityType.ORGANIZATION
        assert scraper._detect_entity_type("Company") == EntityType.ORGANIZATION
        assert scraper._detect_entity_type("corporate") == EntityType.ORGANIZATION

    def test_detect_entity_type_vessel(self):
        """Test vessel type detection."""
        scraper = OFACScraper()

        assert scraper._detect_entity_type("Vessel") == EntityType.VESSEL
        assert scraper._detect_entity_type("SHIP") == EntityType.VESSEL
        assert scraper._detect_entity_type("boat") == EntityType.VESSEL

    def test_detect_entity_type_aircraft(self):
        """Test aircraft type detection."""
        scraper = OFACScraper()

        assert scraper._detect_entity_type("Aircraft") == EntityType.AIRCRAFT
        assert scraper._detect_entity_type("AIRPLANE") == EntityType.AIRCRAFT

    def test_detect_entity_type_unknown(self):
        """Test unknown type detection."""
        scraper = OFACScraper()

        assert scraper._detect_entity_type(None) == EntityType.UNKNOWN
        assert scraper._detect_entity_type("") == EntityType.UNKNOWN
        assert scraper._detect_entity_type("something_else") == EntityType.UNKNOWN

    def test_clean_text(self):
        """Test text cleaning."""
        scraper = OFACScraper()

        assert scraper._clean_text("  hello   world  ") == "hello world"
        assert scraper._clean_text("single") == "single"
        assert scraper._clean_text(None) is None
        assert scraper._clean_text("") is None


class TestOFACScraper:
    """Tests for the OFAC SDN scraper."""

    def test_source_property(self):
        """Test source property."""
        scraper = OFACScraper()
        assert scraper.source == DataSource.OFAC_SDN

    def test_url_property(self):
        """Test URL property."""
        scraper = OFACScraper()
        assert "ofac" in scraper.url.lower() or "treasury" in scraper.url.lower()

    @pytest.mark.asyncio
    async def test_parse_individual(self):
        """Test parsing an individual entry."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>12345</uid>
                <sdnType>Individual</sdnType>
                <firstName>John</firstName>
                <lastName>Smith</lastName>
                <programList>
                    <program>SDGT</program>
                </programList>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].source_uid == "12345"
        assert entities[0].primary_name == "John Smith"
        assert entities[0].entity_type == EntityType.INDIVIDUAL
        assert "SDGT" in entities[0].programs

    @pytest.mark.asyncio
    async def test_parse_organization(self):
        """Test parsing an organization entry."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>67890</uid>
                <sdnType>Entity</sdnType>
                <lastName>ACME Corporation</lastName>
                <programList>
                    <program>IEEPA</program>
                </programList>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].source_uid == "67890"
        assert entities[0].primary_name == "ACME Corporation"
        assert entities[0].entity_type == EntityType.ORGANIZATION

    @pytest.mark.asyncio
    async def test_parse_with_aliases(self):
        """Test parsing entry with aliases."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>11111</uid>
                <sdnType>Individual</sdnType>
                <firstName>Mohammad</firstName>
                <lastName>Ali Khan</lastName>
                <akaList>
                    <aka>
                        <type>a.k.a.</type>
                        <firstName>Mohammed</firstName>
                        <lastName>Ali</lastName>
                    </aka>
                </akaList>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert len(entities[0].names) >= 2  # Primary + alias

    @pytest.mark.asyncio
    async def test_parse_with_address(self):
        """Test parsing entry with address."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>22222</uid>
                <sdnType>Individual</sdnType>
                <lastName>Test Person</lastName>
                <addressList>
                    <address>
                        <country>Russia</country>
                        <city>Moscow</city>
                        <address1>123 Main St</address1>
                    </address>
                </addressList>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert len(entities[0].addresses) >= 1
        assert entities[0].addresses[0]["country"] == "Russia"
        assert entities[0].addresses[0]["city"] == "Moscow"

    @pytest.mark.asyncio
    async def test_parse_with_identifiers(self):
        """Test parsing entry with identification documents."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>33333</uid>
                <sdnType>Individual</sdnType>
                <lastName>Test Person</lastName>
                <idList>
                    <id>
                        <idType>Passport</idType>
                        <idNumber>AB123456</idNumber>
                        <idCountry>Iran</idCountry>
                    </id>
                </idList>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert len(entities[0].identifiers) >= 1
        assert entities[0].identifiers[0]["type"] == "PASSPORT"
        assert entities[0].identifiers[0]["value"] == "AB123456"

    @pytest.mark.asyncio
    async def test_parse_empty_list(self):
        """Test parsing empty SDN list."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_parse_invalid_entry(self):
        """Test that invalid entries are skipped."""
        scraper = OFACScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <sdnEntry>
                <uid>44444</uid>
                <sdnType>Individual</sdnType>
                <!-- Missing lastName, should be skipped -->
            </sdnEntry>
            <sdnEntry>
                <uid>55555</uid>
                <sdnType>Individual</sdnType>
                <lastName>Valid Person</lastName>
            </sdnEntry>
        </sdnList>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].source_uid == "55555"

    def test_map_sdn_type(self):
        """Test SDN type mapping."""
        scraper = OFACScraper()

        assert scraper._map_sdn_type("Individual") == EntityType.INDIVIDUAL
        assert scraper._map_sdn_type("ENTITY") == EntityType.ORGANIZATION
        assert scraper._map_sdn_type("Vessel") == EntityType.VESSEL
        assert scraper._map_sdn_type("Aircraft") == EntityType.AIRCRAFT
        assert scraper._map_sdn_type(None) == EntityType.UNKNOWN

    def test_map_id_type(self):
        """Test ID type mapping."""
        scraper = OFACScraper()

        assert scraper._map_id_type("Passport") == "PASSPORT"
        assert scraper._map_id_type("National ID") == "NATIONAL_ID"
        assert scraper._map_id_type("SSN") == "SSN"
        assert scraper._map_id_type("Tax ID") == "TAX_ID"
        assert scraper._map_id_type("unknown") == "OTHER"
        assert scraper._map_id_type(None) == "OTHER"


class TestUNScraper:
    """Tests for the UN sanctions list scraper."""

    def test_source_property(self):
        """Test source property."""
        scraper = UNScraper()
        assert scraper.source == DataSource.UN

    def test_url_property(self):
        """Test URL property."""
        scraper = UNScraper()
        assert "un.org" in scraper.url.lower() or "scsanctions" in scraper.url.lower()

    @pytest.mark.asyncio
    async def test_parse_individual(self):
        """Test parsing an individual entry."""
        scraper = UNScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <DATAID>6908</DATAID>
                    <FIRST_NAME>ABDUL</FIRST_NAME>
                    <SECOND_NAME>RAHMAN</SECOND_NAME>
                    <THIRD_NAME>KHAN</THIRD_NAME>
                    <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
                </INDIVIDUAL>
            </INDIVIDUALS>
        </CONSOLIDATED_LIST>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].source_uid == "6908"
        assert "ABDUL" in entities[0].primary_name
        assert "RAHMAN" in entities[0].primary_name
        assert entities[0].entity_type == EntityType.INDIVIDUAL

    @pytest.mark.asyncio
    async def test_parse_entity(self):
        """Test parsing an organization entry."""
        scraper = UNScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <ENTITIES>
                <ENTITY>
                    <DATAID>7001</DATAID>
                    <FIRST_NAME>TEST ORGANIZATION</FIRST_NAME>
                    <UN_LIST_TYPE>Taliban</UN_LIST_TYPE>
                </ENTITY>
            </ENTITIES>
        </CONSOLIDATED_LIST>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].source_uid == "7001"
        assert entities[0].primary_name == "TEST ORGANIZATION"
        assert entities[0].entity_type == EntityType.ORGANIZATION

    @pytest.mark.asyncio
    async def test_parse_with_dob(self):
        """Test parsing entry with date of birth."""
        scraper = UNScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <DATAID>6909</DATAID>
                    <FIRST_NAME>Test</FIRST_NAME>
                    <SECOND_NAME>Person</SECOND_NAME>
                    <INDIVIDUAL_DATE_OF_BIRTH>
                        <DATE>1970-01-01</DATE>
                    </INDIVIDUAL_DATE_OF_BIRTH>
                </INDIVIDUAL>
            </INDIVIDUALS>
        </CONSOLIDATED_LIST>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].date_of_birth == "1970-01-01"

    @pytest.mark.asyncio
    async def test_parse_with_nationality(self):
        """Test parsing entry with nationality."""
        scraper = UNScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <DATAID>6910</DATAID>
                    <FIRST_NAME>Test</FIRST_NAME>
                    <SECOND_NAME>Person</SECOND_NAME>
                    <NATIONALITY>
                        <VALUE>Afghan</VALUE>
                    </NATIONALITY>
                </INDIVIDUAL>
            </INDIVIDUALS>
        </CONSOLIDATED_LIST>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 1
        assert entities[0].nationality == "Afghan"

    @pytest.mark.asyncio
    async def test_parse_mixed_entries(self):
        """Test parsing both individuals and entities."""
        scraper = UNScraper()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <CONSOLIDATED_LIST>
            <INDIVIDUALS>
                <INDIVIDUAL>
                    <DATAID>1001</DATAID>
                    <FIRST_NAME>Person</FIRST_NAME>
                    <SECOND_NAME>One</SECOND_NAME>
                </INDIVIDUAL>
            </INDIVIDUALS>
            <ENTITIES>
                <ENTITY>
                    <DATAID>2001</DATAID>
                    <FIRST_NAME>Organization One</FIRST_NAME>
                </ENTITY>
            </ENTITIES>
        </CONSOLIDATED_LIST>
        """

        entities = await scraper._parse(xml_content)

        assert len(entities) == 2

        individuals = [e for e in entities if e.entity_type == EntityType.INDIVIDUAL]
        organizations = [e for e in entities if e.entity_type == EntityType.ORGANIZATION]

        assert len(individuals) == 1
        assert len(organizations) == 1

    def test_map_doc_type(self):
        """Test document type mapping."""
        scraper = UNScraper()

        assert scraper._map_doc_type("Passport") == "PASSPORT"
        assert scraper._map_doc_type("National Identification") == "NATIONAL_ID"
        assert scraper._map_doc_type("unknown") == "OTHER"
        assert scraper._map_doc_type(None) == "OTHER"


class TestEUScraper:
    """Tests for the EU sanctions list scraper."""

    def test_source_property(self):
        """Test source property."""
        scraper = EUScraper()
        assert scraper.source == DataSource.EU

    def test_url_property(self):
        """Test URL property."""
        scraper = EUScraper()
        assert "europa" in scraper.url.lower() or "eu" in scraper.url.lower()


class TestUKScraper:
    """Tests for the UK HMT sanctions list scraper."""

    def test_source_property(self):
        """Test source property."""
        scraper = UKScraper()
        assert scraper.source == DataSource.UK

    def test_url_property(self):
        """Test URL property."""
        scraper = UKScraper()
        assert "gov.uk" in scraper.url.lower() or "assets" in scraper.url.lower()


class TestScraperIntegration:
    """Integration tests verifying all scrapers share common interface."""

    def test_all_scrapers_have_required_properties(self):
        """Test all scrapers implement required properties."""
        scrapers = [OFACScraper(), UNScraper(), EUScraper(), UKScraper()]

        for scraper in scrapers:
            assert hasattr(scraper, "source")
            assert hasattr(scraper, "url")
            assert isinstance(scraper.source, DataSource)
            assert isinstance(scraper.url, str)
            assert len(scraper.url) > 0

    def test_all_scrapers_inherit_from_base(self):
        """Test all scrapers inherit from BaseScraper."""
        scrapers = [OFACScraper(), UNScraper(), EUScraper(), UKScraper()]

        for scraper in scrapers:
            assert isinstance(scraper, BaseScraper)

    def test_all_scrapers_have_common_methods(self):
        """Test all scrapers have common utility methods."""
        scrapers = [OFACScraper(), UNScraper(), EUScraper(), UKScraper()]

        for scraper in scrapers:
            assert callable(getattr(scraper, "scrape", None))
            assert callable(getattr(scraper, "_parse", None))
            assert callable(getattr(scraper, "_hash_content", None))
            assert callable(getattr(scraper, "_clean_text", None))
