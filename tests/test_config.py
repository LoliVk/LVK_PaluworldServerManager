from lvk_paluworld_server_manager.config import AppConfig, create_app_message


def test_create_app_message_default() -> None:
    message = create_app_message()
    assert message == "LVK Palworld Server Manager is ready."


def test_create_app_message_custom() -> None:
    config = AppConfig(title="Demo App")
    message = create_app_message(config)
    assert message == "Demo App is ready."
