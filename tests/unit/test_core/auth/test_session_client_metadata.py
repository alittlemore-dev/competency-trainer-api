from ua_parser import parse

from core.auth.enums import AuthSessionDeviceTypeEnum
from core.auth.schemas import AuthSessionClientMetadata


class TestAuthSessionClientMetadata:
    def test_device_type_enum_maps_parser_device_type(self) -> None:
        assert AuthSessionDeviceTypeEnum.from_device_type("Computer") == (
            AuthSessionDeviceTypeEnum.DESKTOP
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("Mac") == (
            AuthSessionDeviceTypeEnum.DESKTOP
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("Mobile") == (
            AuthSessionDeviceTypeEnum.MOBILE
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("iPhone") == (
            AuthSessionDeviceTypeEnum.MOBILE
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("Tablet") == (
            AuthSessionDeviceTypeEnum.TABLET
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("iPad") == (
            AuthSessionDeviceTypeEnum.TABLET
        )
        assert AuthSessionDeviceTypeEnum.from_device_type("Bot") == (AuthSessionDeviceTypeEnum.BOT)
        assert AuthSessionDeviceTypeEnum.from_device_type("") == AuthSessionDeviceTypeEnum.UNKNOWN
        assert AuthSessionDeviceTypeEnum.from_device_type(None) == (
            AuthSessionDeviceTypeEnum.UNKNOWN
        )

    def test_create_builds_privacy_safe_labels_from_parsed_user_agent_parts(self) -> None:
        metadata = AuthSessionClientMetadata.create(
            browser="Chrome",
            operating_system="Linux",
            device_type="Mac",
        )

        assert metadata == AuthSessionClientMetadata(
            user_agent_display="Chrome on Linux",
            user_agent_browser="Chrome",
            user_agent_os="Linux",
            user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
        )

    def test_create_accepts_ua_parser_output_without_persisting_raw_user_agent(
        self,
    ) -> None:
        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        result = parse(user_agent)

        metadata = AuthSessionClientMetadata.create(
            browser=result.user_agent.family if result.user_agent else None,
            operating_system=result.os.family if result.os else None,
            device_type=result.device.family if result.device else None,
        )

        assert metadata == AuthSessionClientMetadata(
            user_agent_display="Chrome on Linux",
            user_agent_browser="Chrome",
            user_agent_os="Linux",
            user_agent_device=AuthSessionDeviceTypeEnum.UNKNOWN,
        )
        assert user_agent not in metadata.user_agent_display

    def test_empty_uses_non_null_unknown_labels(self) -> None:
        assert AuthSessionClientMetadata.empty() == AuthSessionClientMetadata(
            user_agent_display="Unknown device",
            user_agent_browser="Unknown browser",
            user_agent_os="Unknown OS",
            user_agent_device=AuthSessionDeviceTypeEnum.UNKNOWN,
        )

    def test_create_uses_unknown_labels_for_unrecognized_parts(self) -> None:
        metadata = AuthSessionClientMetadata.create(
            browser=None,
            operating_system=None,
            device_type=None,
        )

        assert metadata == AuthSessionClientMetadata(
            user_agent_display="Unknown device",
            user_agent_browser="Unknown browser",
            user_agent_os="Unknown OS",
            user_agent_device=AuthSessionDeviceTypeEnum.UNKNOWN,
        )
