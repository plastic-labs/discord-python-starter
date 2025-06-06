from honcho import Honcho


def get_user_collection(honcho_client: Honcho, app_id: str, user_id: str):
    """Get a Honcho user collection object for the message author"""
    try:
        collection = honcho_client.apps.users.collections.get_by_name(
            name=user_id, app_id=app_id, user_id=user_id
        )
    except Exception:
        collection = honcho_client.apps.users.collections.create(
            user_id=user_id, app_id=app_id, name=user_id
        )
    return collection


def get_session(
    honcho: Honcho, app_id: str, user_id: str, custom_metadata: dict, create=False
):
    """
    Get an existing session for the user and location or optionally create a new one if none exists.
    Returns a tuple of (session, is_new) where is_new indicates if a new session was created.
    """
    # Query for active sessions with both user_id and location_id
    # This should return a single session
    sessions_iter = honcho.apps.users.sessions.list(
        app_id=app_id, user_id=user_id, is_active=True, filter=custom_metadata
    )
    sessions = list(session for session in sessions_iter)

    if sessions:
        return sessions[0], False

    # If no session is found and create is True, create a new one
    if create:
        print("No active session found, creating new one")
        return (
            honcho.apps.users.sessions.create(
                user_id=user_id,
                app_id=app_id,
                metadata=custom_metadata,
            ),
            True,
        )

    return None, False
