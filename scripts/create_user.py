#!/usr/bin/env python3
"""
Script to create a user in the ATOL database.
This is useful for creating the first user in the system.
"""

import argparse
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import from app
sys.path.append("/Users/emilylm/Repositories/atol-database-v2")

from app.core.security import get_password_hash
from app.db.session import Base
from app.models.user import User


def create_user(db_uri, username, email, password, role, full_name=None):
    """Create a user in the database."""
    # Create SQLAlchemy engine and session
    engine = create_engine(db_uri)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"User with username '{username}' already exists.")
            return False

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"User with email '{email}' already exists.")
            return False

        is_superuser = True if role == "superuser" else False

        # Create new superuser
        db_user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            roles=[role],
            is_active=True,
            is_superuser=is_superuser,
        )

        # Add user to database
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        print(f"User '{username}' created successfully with ID: {db_user.id}")
        return True

    except Exception as e:
        print(f"Error creating user: {e}")
        return False

    finally:
        db.close()


def main():
    """Main function to parse arguments and create user."""
    parser = argparse.ArgumentParser(description="Create a user in the ATOL database")

    # Database connection parameters
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", default="5433", help="Database port")
    parser.add_argument("--dbname", default="atol_database", help="Database name")
    parser.add_argument("--user", default="postgres", help="Database user")
    parser.add_argument("--password", default="postgres", help="Database password")
    parser.add_argument(
        "--db-uri", help="Full database URI (overrides individual connection parameters)"
    )

    # User parameters
    parser.add_argument("--username", required=True, help="Username for the user")
    parser.add_argument("--email", required=True, help="Email for the user")
    parser.add_argument("--user-password", required=True, help="Password for the user")
    parser.add_argument("--full-name", help="Full name for the user")
    parser.add_argument("--role", help="Role for the user")

    args = parser.parse_args()

    # Construct database URI if not provided
    if args.db_uri:
        db_uri = args.db_uri
    else:
        db_uri = f"postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.dbname}"

    # Create user
    create_user(
        db_uri=db_uri,
        username=args.username,
        email=args.email,
        password=args.user_password,
        role=args.role,
        full_name=args.full_name,
    )


if __name__ == "__main__":
    main()
