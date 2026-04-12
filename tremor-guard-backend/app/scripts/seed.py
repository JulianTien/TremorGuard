from app.db.session import ClinicalSessionLocal, IdentitySessionLocal
from app.services.seeds import seed_clinical, seed_identity


def main() -> None:
    with IdentitySessionLocal() as identity_session:
        user_id = seed_identity(identity_session)

    with ClinicalSessionLocal() as clinical_session:
        seed_clinical(clinical_session, user_id)


if __name__ == "__main__":
    main()
