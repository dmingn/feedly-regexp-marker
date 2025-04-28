from unittest.mock import MagicMock, call

import pytest
from feedly.api_client.session import FeedlySession
from pytest_mock import MockerFixture

from feedly_regexp_marker.feedly_client import Action, Entry, FeedlyClient

# --- Test FeedlyClient ---


@pytest.fixture
def mock_session(mocker: MockerFixture) -> MagicMock:
    """Fixture to return a mock of FeedlySession instance."""
    # Specify spec=FeedlySession to mimic the interface
    session_mock = mocker.MagicMock(spec=FeedlySession)
    # Mock the user.id property
    session_mock.user = mocker.MagicMock()
    session_mock.user.id = "test_user_id_mocked"
    return session_mock


@pytest.fixture
def feedly_client(mock_session: MagicMock) -> FeedlyClient:
    """Fixture to create a FeedlyClient instance for testing."""
    # Pass the mock session directly (DI)
    return FeedlyClient(session=mock_session)


class TestFeedlyClient:
    def test_init(self, mock_session: MagicMock):
        """Test FeedlyClient initialization sets the session correctly."""
        client = FeedlyClient(session=mock_session)
        assert client.session is mock_session

    # --- Test fetch_all_unread_entries ---
    def test_fetch_all_unread_entries_single_page(self, feedly_client: FeedlyClient):
        """Test fetching when API returns all entries in one page."""
        entry_data1 = {"id": "e1", "title": "Entry 1"}
        entry_data2 = {"id": "e2", "title": "Entry 2"}
        api_response = {
            "items": [entry_data1, entry_data2],
            "continuation": None,  # No continuation
        }
        # Set the API response
        feedly_client.session.do_api_request.return_value = api_response

        # Convert the generator to a list and verify the results
        entries = list(feedly_client.fetch_all_unread_entries())

        # Check API call parameters.
        expected_params = {
            "streamId": "user/test_user_id_mocked/category/global.all",
            "count": "1000",
            "ranked": "oldest",
            "unreadOnly": "true",
        }
        feedly_client.session.do_api_request.assert_called_once_with(
            relative_url="/v3/streams/contents", params=expected_params
        )

        # Check result (whether it has been converted to a Pydantic model).
        assert len(entries) == 2
        assert entries[0].id == "e1"
        assert entries[1].id == "e2"
        assert isinstance(entries[0], Entry)
        assert isinstance(entries[1], Entry)

    def test_fetch_all_unread_entries_multiple_pages(self, feedly_client: FeedlyClient):
        """Test fetching handles pagination correctly via loop."""
        entry_data1 = {"id": "e1"}
        entry_data2 = {"id": "e2"}
        entry_data3 = {"id": "e3"}

        # Define responses for each API call
        api_response_page1 = {
            "items": [entry_data1, entry_data2],
            "continuation": "cont1",
        }
        api_response_page2 = {"items": [entry_data3], "continuation": None}  # Last page

        # Use side_effect to return different values for subsequent calls
        feedly_client.session.do_api_request.side_effect = [
            api_response_page1,
            api_response_page2,
        ]

        # Convert the generator to a list and verify the results.
        entries = list(feedly_client.fetch_all_unread_entries())

        # Check API call parameters for both calls.
        base_params = {
            "streamId": "user/test_user_id_mocked/category/global.all",
            "count": "1000",
            "ranked": "oldest",
            "unreadOnly": "true",
        }
        expected_calls = [
            call(relative_url="/v3/streams/contents", params=base_params),  # First call
            call(
                relative_url="/v3/streams/contents",
                params={**base_params, "continuation": "cont1"},
            ),  # Second call
        ]
        feedly_client.session.do_api_request.assert_has_calls(expected_calls)
        assert feedly_client.session.do_api_request.call_count == 2

        # Check result (all items combined).
        assert len(entries) == 3
        assert entries[0].id == "e1"
        assert entries[1].id == "e2"
        assert entries[2].id == "e3"
        assert all(isinstance(e, Entry) for e in entries)

    def test_fetch_all_unread_entries_stops_on_empty_items(
        self, feedly_client: FeedlyClient
    ):
        """Test fetching stops when API returns empty items even with continuation."""
        entry_data1 = {"id": "e1"}
        api_response_page1 = {"items": [entry_data1], "continuation": "cont1"}
        api_response_page2 = {"items": [], "continuation": "cont2"}  # Empty items

        feedly_client.session.do_api_request.side_effect = [
            api_response_page1,
            api_response_page2,
        ]

        entries = list(feedly_client.fetch_all_unread_entries())

        # Check API calls (should only be two).
        assert feedly_client.session.do_api_request.call_count == 2
        # Check result (only items from the first page).
        assert len(entries) == 1
        assert entries[0].id == "e1"

    def test_fetch_all_unread_entries_no_entries(self, feedly_client: FeedlyClient):
        """Test fetch_all_unread_entries when API returns no entries initially."""
        api_response: dict = {"items": [], "continuation": None}
        feedly_client.session.do_api_request.return_value = api_response

        entries = list(feedly_client.fetch_all_unread_entries())

        feedly_client.session.do_api_request.assert_called_once()
        assert entries == []

    # --- Test mark_entries / save_entries / read_entries ---
    def test_mark_entries_dry_run(
        self, mocker: MockerFixture, feedly_client: FeedlyClient
    ):
        """Test mark_entries with dry_run=True prints titles and doesn't call the API."""
        mock_print = mocker.patch("builtins.print")  # Mock the built-in print function.
        entry1 = Entry(id="e1", title="Title 1")
        entry2 = Entry(id="e2", title="Title 2")
        # Also test passing a generator as input.
        entries_to_mark_gen = (e for e in [entry1, entry2])

        feedly_client.mark_entries(
            entries=entries_to_mark_gen, action="markAsRead", dry_run=True
        )
        # Check API was NOT called
        feedly_client.session.do_api_request.assert_not_called()
        # Check print was called with the list of titles
        # Note: The generator is consumed by the list comprehension inside mark_entries
        mock_print.assert_called_once_with(["Title 1", "Title 2"])

    def test_mark_entries_empty_iterable(self, feedly_client: FeedlyClient):
        """Test mark_entries with an empty iterable doesn't call API."""
        entries_to_mark: list[Entry] = []  # Empty list.
        feedly_client.mark_entries(
            entries=entries_to_mark, action="markAsRead", dry_run=False
        )
        feedly_client.session.do_api_request.assert_not_called()

        feedly_client.mark_entries(
            entries=entries_to_mark, action="markAsSaved", dry_run=False
        )
        feedly_client.session.do_api_request.assert_not_called()

    @pytest.mark.parametrize("action_to_test", ["markAsRead", "markAsSaved"])
    def test_mark_entries_api_call(
        self, feedly_client: FeedlyClient, action_to_test: Action
    ):
        """Test mark_entries calls the correct API endpoint with correct data."""
        entry1 = Entry(id="id_e1", title="Title 1")
        entry2 = Entry(id="id_e2", title="Title 2")
        # Pass the generator as input.
        entries_to_mark_gen = (e for e in [entry1, entry2])

        feedly_client.mark_entries(
            entries=entries_to_mark_gen, action=action_to_test, dry_run=False
        )

        expected_data = {
            "action": action_to_test,
            "type": "entries",
            "entryIds": ["id_e1", "id_e2"],  # List comprehension consumes the generator
        }
        feedly_client.session.do_api_request.assert_called_once_with(
            relative_url="/v3/markers", data=expected_data
        )

    def test_save_entries_calls_mark(
        self, mocker: MockerFixture, feedly_client: FeedlyClient
    ):
        """Test save_entries calls mark_entries with correct action."""
        entry1 = Entry(id="e1")
        entries = [entry1]
        # Mock the mark_entries method.
        mock_mark = mocker.patch.object(feedly_client, "mark_entries")
        feedly_client.save_entries(entries=entries, dry_run=False)
        # Check if it was called with action="markAsSaved"
        mock_mark.assert_called_once_with(
            entries=entries, action="markAsSaved", dry_run=False
        )

    def test_read_entries_calls_mark(
        self, mocker: MockerFixture, feedly_client: FeedlyClient
    ):
        """Test read_entries calls mark_entries with correct action."""
        entry1 = Entry(id="e1")
        entries = [entry1]
        # Mock the mark_entries method.
        mock_mark = mocker.patch.object(feedly_client, "mark_entries")
        feedly_client.read_entries(entries=entries, dry_run=False)
        # Check if it was called with action="markAsRead"
        mock_mark.assert_called_once_with(
            entries=entries, action="markAsRead", dry_run=False
        )
