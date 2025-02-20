"""Tests for arcam fmj receivers."""
from math import isclose
from unittest.mock import ANY, MagicMock, PropertyMock, patch

from arcam.fmj import DecodeMode2CH, DecodeModeMCH, SourceCodes
import pytest

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    MEDIA_TYPE_MUSIC,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID

from .conftest import MOCK_HOST, MOCK_NAME, MOCK_PORT, MOCK_UUID

MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}


async def update(player, force_refresh=False):
    """Force a update of player and return current state data."""
    await player.async_update_ha_state(force_refresh=force_refresh)
    return player.hass.states.get(player.entity_id)


async def test_properties(player, state):
    """Test standard properties."""
    assert player.unique_id == f"{MOCK_UUID}-1"
    assert player.device_info == {
        "name": f"Arcam FMJ ({MOCK_HOST})",
        "identifiers": {("arcam_fmj", MOCK_UUID), ("arcam_fmj", MOCK_HOST, MOCK_PORT)},
        "model": "Arcam FMJ AVR",
        "manufacturer": "Arcam",
    }
    assert not player.should_poll


async def test_powered_off(hass, player, state):
    """Test properties in powered off state."""
    state.get_source.return_value = None
    state.get_power.return_value = None

    data = await update(player)
    assert "source" not in data.attributes
    assert data.state == "off"


async def test_powered_on(player, state):
    """Test properties in powered on state."""
    state.get_source.return_value = SourceCodes.PVR
    state.get_power.return_value = True

    data = await update(player)
    assert data.attributes["source"] == "PVR"
    assert data.state == "on"


async def test_supported_features(player, state):
    """Test supported features."""
    data = await update(player)
    assert data.attributes["supported_features"] == 200588


async def test_turn_on(player, state):
    """Test turn on service."""
    state.get_power.return_value = None
    await player.async_turn_on()
    state.set_power.assert_not_called()

    state.get_power.return_value = False
    await player.async_turn_on()
    state.set_power.assert_called_with(True)


async def test_turn_off(player, state):
    """Test command to turn off."""
    await player.async_turn_off()
    state.set_power.assert_called_with(False)


@pytest.mark.parametrize("mute", [True, False])
async def test_mute_volume(player, state, mute):
    """Test mute functionality."""
    await player.async_mute_volume(mute)
    state.set_mute.assert_called_with(mute)
    player.async_write_ha_state.assert_called_with()


async def test_name(player):
    """Test name."""
    assert player.name == f"{MOCK_NAME} - Zone: 1"


async def test_update(player, state):
    """Test update."""
    await update(player, force_refresh=True)
    state.update.assert_called_with()


@pytest.mark.parametrize(
    "source, value",
    [("PVR", SourceCodes.PVR), ("BD", SourceCodes.BD), ("INVALID", None)],
)
async def test_select_source(hass, player_setup, state, source, value):
    """Test selection of source."""
    await hass.services.async_call(
        "media_player",
        SERVICE_SELECT_SOURCE,
        service_data={ATTR_ENTITY_ID: player_setup, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    if value:
        state.set_source.assert_called_with(value)
    else:
        state.set_source.assert_not_called()


async def test_source_list(player, state):
    """Test source list."""
    state.get_source_list.return_value = [SourceCodes.BD]
    data = await update(player)
    assert data.attributes["source_list"] == ["BD"]


@pytest.mark.parametrize(
    "mode",
    [
        ("STEREO"),
        ("DOLBY_PL"),
    ],
)
async def test_select_sound_mode(player, state, mode):
    """Test selection sound mode."""
    await player.async_select_sound_mode(mode)
    state.set_decode_mode.assert_called_with(mode)


async def test_volume_up(player, state):
    """Test mute functionality."""
    await player.async_volume_up()
    state.inc_volume.assert_called_with()
    player.async_write_ha_state.assert_called_with()


async def test_volume_down(player, state):
    """Test mute functionality."""
    await player.async_volume_down()
    state.dec_volume.assert_called_with()
    player.async_write_ha_state.assert_called_with()


@pytest.mark.parametrize(
    "mode, mode_enum",
    [
        ("STEREO", DecodeMode2CH.STEREO),
        ("STEREO_DOWNMIX", DecodeModeMCH.STEREO_DOWNMIX),
        (None, None),
    ],
)
async def test_sound_mode(player, state, mode, mode_enum):
    """Test selection sound mode."""
    state.get_decode_mode.return_value = mode_enum
    data = await update(player)
    assert data.attributes.get(ATTR_SOUND_MODE) == mode


@pytest.mark.parametrize(
    "modes, modes_enum",
    [
        (["STEREO", "DOLBY_PL"], [DecodeMode2CH.STEREO, DecodeMode2CH.DOLBY_PL]),
        (["STEREO_DOWNMIX"], [DecodeModeMCH.STEREO_DOWNMIX]),
        (None, None),
    ],
)
async def test_sound_mode_list(player, state, modes, modes_enum):
    """Test sound mode list."""
    state.get_decode_modes.return_value = modes_enum
    data = await update(player)
    assert data.attributes.get(ATTR_SOUND_MODE_LIST) == modes


async def test_is_volume_muted(player, state):
    """Test muted."""
    state.get_mute.return_value = True
    assert player.is_volume_muted is True  # pylint: disable=singleton-comparison
    state.get_mute.return_value = False
    assert player.is_volume_muted is False  # pylint: disable=singleton-comparison
    state.get_mute.return_value = None
    assert player.is_volume_muted is None


async def test_volume_level(player, state):
    """Test volume."""
    state.get_volume.return_value = 0
    assert isclose(player.volume_level, 0.0)
    state.get_volume.return_value = 50
    assert isclose(player.volume_level, 50.0 / 99)
    state.get_volume.return_value = 99
    assert isclose(player.volume_level, 1.0)
    state.get_volume.return_value = None
    assert player.volume_level is None


@pytest.mark.parametrize("volume, call", [(0.0, 0), (0.5, 50), (1.0, 99)])
async def test_set_volume_level(player, state, volume, call):
    """Test setting volume."""
    await player.async_set_volume_level(volume)
    state.set_volume.assert_called_with(call)


@pytest.mark.parametrize(
    "source, media_content_type",
    [
        (SourceCodes.DAB, MEDIA_TYPE_MUSIC),
        (SourceCodes.FM, MEDIA_TYPE_MUSIC),
        (SourceCodes.PVR, None),
        (None, None),
    ],
)
async def test_media_content_type(player, state, source, media_content_type):
    """Test content type deduction."""
    state.get_source.return_value = source
    assert player.media_content_type == media_content_type


@pytest.mark.parametrize(
    "source, dab, rds, channel",
    [
        (SourceCodes.DAB, "dab", "rds", "dab"),
        (SourceCodes.DAB, None, None, None),
        (SourceCodes.FM, "dab", "rds", "rds"),
        (SourceCodes.FM, None, None, None),
        (SourceCodes.PVR, "dab", "rds", None),
    ],
)
async def test_media_channel(player, state, source, dab, rds, channel):
    """Test media channel."""
    state.get_dab_station.return_value = dab
    state.get_rds_information.return_value = rds
    state.get_source.return_value = source
    assert player.media_channel == channel


@pytest.mark.parametrize(
    "source, dls, artist",
    [
        (SourceCodes.DAB, "dls", "dls"),
        (SourceCodes.FM, "dls", None),
        (SourceCodes.DAB, None, None),
    ],
)
async def test_media_artist(player, state, source, dls, artist):
    """Test media artist."""
    state.get_dls_pdt.return_value = dls
    state.get_source.return_value = source
    assert player.media_artist == artist


@pytest.mark.parametrize(
    "source, channel, title",
    [
        (SourceCodes.DAB, "channel", "DAB - channel"),
        (SourceCodes.DAB, None, "DAB"),
        (None, None, None),
    ],
)
async def test_media_title(player, state, source, channel, title):
    """Test media title."""
    from homeassistant.components.arcam_fmj.media_player import ArcamFmj

    state.get_source.return_value = source
    with patch.object(
        ArcamFmj, "media_channel", new_callable=PropertyMock
    ) as media_channel:
        media_channel.return_value = channel
        data = await update(player)
        if title is None:
            assert "media_title" not in data.attributes
        else:
            assert data.attributes["media_title"] == title


async def test_added_to_hass(player, state):
    """Test addition to hass."""
    from homeassistant.components.arcam_fmj.const import (
        SIGNAL_CLIENT_DATA,
        SIGNAL_CLIENT_STARTED,
        SIGNAL_CLIENT_STOPPED,
    )

    connectors = {}

    def _connect(signal, fun):
        connectors[signal] = fun

    player.hass = MagicMock()
    player.hass.helpers.dispatcher.async_dispatcher_connect.side_effects = _connect

    await player.async_added_to_hass()
    state.start.assert_called_with()
    player.hass.helpers.dispatcher.async_dispatcher_connect.assert_any_call(
        SIGNAL_CLIENT_DATA, ANY
    )
    player.hass.helpers.dispatcher.async_dispatcher_connect.assert_any_call(
        SIGNAL_CLIENT_STARTED, ANY
    )
    player.hass.helpers.dispatcher.async_dispatcher_connect.assert_any_call(
        SIGNAL_CLIENT_STOPPED, ANY
    )
