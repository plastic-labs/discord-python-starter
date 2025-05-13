from contextlib import contextmanager
from typing import Generator
from honcho import Honcho

@contextmanager
def honcho_transaction(honcho: Honcho) -> Generator[Honcho, None, None]:
    """
    A context manager that automatically handles Honcho transaction lifecycle.
    Modifies the client's headers to include the transaction ID for all requests.
    
    Args:
        honcho: The base Honcho client instance
        
    Yields:
        The same Honcho client instance with transaction headers attached
        
    Example:
        ```python
        with honcho_transaction(honcho) as honcho_txn:
            # All requests made with honcho_txn will include the transaction ID header
            message = honcho_txn.apps.users.sessions.messages.create(...)
        ```

    Detailed Example:
        ```python
        honcho = Honcho()
        app = honcho.apps.get_or_create(name="test-app")

        print(f"Honcho app acquired with id {app.id}")

        user = honcho.apps.users.get_or_create(app_id=app.id, name="hello")
        session = honcho.apps.users.sessions.create(app_id=app.id, user_id=user.id)

        with honcho_transaction(honcho) as honcho_txn:
            message = honcho_txn.apps.users.sessions.messages.create(
                app_id=app.id,
                session_id=session.id,
                user_id=user.id,
                is_user=True,
                content="Hello, how are you?",
            )

            # within the transaction, the message is visible
            message = honcho_txn.apps.users.sessions.messages.get(message.id, app_id=app.id, session_id=session.id, user_id=user.id)
            assert message.content == "Hello, how are you?"

            # List all messages will fail, because the transaction is not yet committed
            # Paginated requests cannot be used inside transactions.
            # messages = honcho_txn.apps.users.sessions.messages.list(app_id=app.id, session_id=session.id, user_id=user.id)

        # after the transaction completes, the message is visible outside
        messages = honcho.apps.users.sessions.messages.list(app_id=app.id, session_id=session.id, user_id=user.id)
        assert messages.total == 1
        ```
    """
    old_transaction_id = honcho.transaction_id
    transaction_id = honcho.transactions.begin()
    
    try:
        # Add transaction ID to custom headers
        honcho.transaction_id = transaction_id
        yield honcho
        honcho.transaction_id = old_transaction_id
        honcho.transactions.commit(transaction_id)
    except Exception:
        honcho.transactions.rollback(transaction_id)
        raise


def get_session(honcho: Honcho, app_id: str, user_id: str, custom_metadata: dict, create=False):
    """Get an existing session for the user and location or optionally create a new one if none exists.
    Returns a tuple of (session, is_new) where is_new indicates if a new session was created."""
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
        return honcho.apps.users.sessions.create(
            user_id=user_id,
            app_id=app_id,
            metadata=custom_metadata,
        ), True

    return None, False