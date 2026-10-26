"""Synthetic demo data. DEMO DATA — NOT REAL STUDENT INFORMATION.

Every institution, person and identifier here is fictional. Identifiers use the deliberately
unreal format DEMO-APAAR-######. Student records are loaded through the same upload pipeline
real submissions use, so dashboards and findings reflect genuinely processed data.

Usage (from backend/):
    python -m app.seed            # load demo data into an empty database
    python -m app.seed --reset    # wipe ALL data, then load demo data
"""

import argparse
import csv
import io
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import utcnow
from app.models import (
    Admission,
    AuditEvent,
    ConsentRecord,
    Finding,
    Institution,
    IntakeConfiguration,
    Programme,
    ReviewAction,
    Student,
    SystemSetting,
    UploadBatch,
    UploadRowResult,
    User,
    UserSession,
    VerifiableRecord,
    VerificationAttempt,
)
from app.services.ingestion.schema import COLUMN_NAMES
from app.services.ingestion.uploads import process_upload
from app.services.records import CONSENT_PURPOSE, issue_record

DEMO_PASSWORD = "Demo@12345"  # noqa: S105 - public, synthetic, local-demo only
CROSS_INSTITUTION_ID = "DEMO-APAAR-300421"

FIRST_NAMES = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Vihaan",
    "Arjun",
    "Sai",
    "Reyansh",
    "Krishna",
    "Ishaan",
    "Shaurya",
    "Atharv",
    "Kabir",
    "Rohan",
    "Dhruv",
    "Arnav",
    "Yash",
    "Pranav",
    "Nikhil",
    "Siddharth",
    "Rahul",
    "Ananya",
    "Diya",
    "Aadhya",
    "Saanvi",
    "Pari",
    "Anika",
    "Navya",
    "Myra",
    "Sara",
    "Ira",
    "Meera",
    "Kavya",
    "Riya",
    "Tanvi",
    "Sneha",
    "Pooja",
    "Lakshmi",
    "Nandini",
    "Shreya",
    "Aditi",
    "Harsh",
    "Manav",
    "Varun",
    "Kunal",
    "Neha",
    "Divya",
    "Farhan",
    "Zoya",
    "Imran",
    "Ayesha",
    "Gurpreet",
    "Harleen",
    "Joseph",
    "Mary",
    "Thomas",
]
LAST_NAMES = [
    "Sharma",
    "Verma",
    "Iyer",
    "Nair",
    "Reddy",
    "Patel",
    "Shah",
    "Mehta",
    "Joshi",
    "Kulkarni",
    "Deshpande",
    "Gupta",
    "Agarwal",
    "Singh",
    "Kaur",
    "Das",
    "Bose",
    "Banerjee",
    "Mukherjee",
    "Pillai",
    "Menon",
    "Rao",
    "Naidu",
    "Chauhan",
    "Yadav",
    "Mishra",
    "Pandey",
    "Tiwari",
    "Khan",
    "Ansari",
    "Fernandes",
    "D'Souza",
    "Thomas",
    "Kurian",
    "Bhat",
    "Hegde",
    "Gowda",
]
FOREIGN_STUDENTS = [
    ("Amara Okafor", "NG"),
    ("Tenzin Dorji", "BT"),
    ("Hamid Rahimi", "AF"),
    ("Nimal Perera", "LK"),
    ("Farida Hossain", "BD"),
    ("Kiran Gurung", "NP"),
    ("Abebe Tesfaye", "ET"),
    ("Lina Haddad", "JO"),
]
OCI_NATIONALITIES = ["US", "GB", "CA", "AU", "SG"]


@dataclass(frozen=True)
class ProgrammeSpec:
    code: str
    name: str
    level: str
    duration: int
    intake: int
    supernumerary: int


@dataclass(frozen=True)
class InstitutionSpec:
    code: str
    name: str
    state: str
    kind: str
    slug: str
    programmes: tuple[ProgrammeSpec, ...]


INSTITUTIONS = (
    InstitutionSpec(
        "DEMO-INST-001",
        "Aranya Institute of Technology (Demo)",
        "Maharashtra",
        "Engineering & Technology",
        "aranya",
        (
            ProgrammeSpec("BTECH-CSE", "B.Tech Computer Science and Engineering", "UG", 4, 60, 3),
            ProgrammeSpec(
                "BTECH-ECE", "B.Tech Electronics and Communication Engineering", "UG", 4, 60, 3
            ),
            ProgrammeSpec("BTECH-ME", "B.Tech Mechanical Engineering", "UG", 4, 60, 3),
            ProgrammeSpec("MTECH-DS", "M.Tech Data Science", "PG", 2, 18, 1),
        ),
    ),
    InstitutionSpec(
        "DEMO-INST-002",
        "Kaveri School of Management (Demo)",
        "Karnataka",
        "Management (PGDM)",
        "kaveri",
        (
            ProgrammeSpec("PGDM-GEN", "PGDM General Management", "PGDM", 2, 120, 6),
            ProgrammeSpec("PGDM-FIN", "PGDM Finance", "PGDM", 2, 60, 3),
            ProgrammeSpec("PGDM-BA", "PGDM Business Analytics", "PGDM", 2, 60, 2),
        ),
    ),
    InstitutionSpec(
        "DEMO-INST-003",
        "Narmada College of Engineering (Demo)",
        "Gujarat",
        "Engineering & Technology",
        "narmada",
        (
            ProgrammeSpec("BTECH-CSE", "B.Tech Computer Science and Engineering", "UG", 4, 60, 3),
            ProgrammeSpec("BTECH-CIVIL", "B.Tech Civil Engineering", "UG", 4, 60, 3),
            ProgrammeSpec("DIP-ME", "Diploma in Mechanical Engineering", "Diploma", 3, 30, 1),
        ),
    ),
    InstitutionSpec(
        "DEMO-INST-004",
        "Brahmaputra Polytechnic (Demo)",
        "Assam",
        "Diploma / Polytechnic",
        "brahmaputra",
        (
            ProgrammeSpec("DIP-CSE", "Diploma in Computer Engineering", "Diploma", 3, 60, 2),
            ProgrammeSpec("DIP-EE", "Diploma in Electrical Engineering", "Diploma", 3, 60, 2),
        ),
    ),
)


def demo_years(today: date) -> tuple[str, str]:
    """(previous, current) academic years. The current year's admissions are complete."""
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start - 1}-{start % 100:02d}", f"{start}-{(start + 1) % 100:02d}"


@dataclass
class Row:
    institution_code: str
    programme_code: str
    academic_year: str
    institution_student_id: str
    apaar_id: str
    full_name: str
    date_of_birth: str
    gender: str
    admission_date: str
    seat_type: str = "REGULAR"
    nri_category: str = "N"
    oci_status: str = "N"
    foreign_national_status: str = "N"
    nationality: str = "IN"
    enrolment_status: str = "ENROLLED"

    def values(self) -> list[str]:
        return [getattr(self, name) for name in COLUMN_NAMES]


def to_csv(rows: list[Row] | list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMN_NAMES)
    for row in rows:
        writer.writerow(row.values() if isinstance(row, Row) else row)
    return buffer.getvalue().encode("utf-8")


class RowFactory:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def person(self) -> tuple[str, str]:
        name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
        gender = self.rng.choice(["F", "M", "M", "F", "M"])
        return name, gender

    def admission_date(self, year: str) -> date:
        start = int(year[:4])
        return date(start, 7, 15) + timedelta(days=self.rng.randint(0, 45))

    def dob(self, admitted: date, level: str) -> date:
        age = self.rng.randint(21, 25) if level in ("PG", "PGDM") else self.rng.randint(17, 19)
        return admitted - timedelta(days=age * 365 + self.rng.randint(0, 300))

    def rows(
        self,
        inst: InstitutionSpec,
        programme: ProgrammeSpec,
        year: str,
        count: int,
        id_start: int,
        sid_prefix: str,
        *,
        supernumerary: int = 0,
    ) -> list[Row]:
        out = []
        for i in range(count + supernumerary):
            admitted = self.admission_date(year)
            name, gender = self.person()
            row = Row(
                institution_code=inst.code,
                programme_code=programme.code,
                academic_year=year,
                institution_student_id=f"{sid_prefix}{i + 1:03d}",
                apaar_id=f"DEMO-APAAR-{id_start + i:06d}",
                full_name=name,
                date_of_birth=self.dob(admitted, programme.level).isoformat(),
                gender=gender,
                admission_date=admitted.isoformat(),
            )
            roll = self.rng.random()
            if i >= count:  # supernumerary seat, e.g. foreign national or OCI admission
                foreign_name, nationality = FOREIGN_STUDENTS[i % len(FOREIGN_STUDENTS)]
                row.full_name = foreign_name
                row.seat_type = "SUPERNUMERARY"
                row.foreign_national_status = "Y"
                row.nationality = nationality
            elif roll < 0.04:
                row.nri_category = "Y"
            elif roll < 0.06:
                row.oci_status = "Y"
                row.nationality = self.rng.choice(OCI_NATIONALITIES)
            out.append(row)
        return out


def _wipe(db: Session) -> None:
    for model in (
        ReviewAction,
        Finding,
        VerifiableRecord,
        VerificationAttempt,
        ConsentRecord,
        UploadRowResult,
        Admission,
        Student,
        UploadBatch,
        IntakeConfiguration,
        Programme,
        AuditEvent,
        UserSession,
        SystemSetting,
        User,
        Institution,
    ):
        db.execute(delete(model))
    db.flush()


def _backdate(db: Session, batch: UploadBatch, days_ago: int) -> None:
    when = utcnow() - timedelta(days=days_ago, hours=random.Random(days_ago).randint(1, 8))
    batch.created_at = when
    batch.completed_at = when + timedelta(seconds=2)
    db.flush()


def _review(
    db: Session,
    finding: Finding,
    actor: User,
    action: str,
    to_status: str,
    comment: str,
    days_ago: int,
) -> None:
    when = utcnow() - timedelta(days=days_ago)
    db.add(
        ReviewAction(
            finding_id=finding.id,
            actor_id=actor.id,
            action=action,
            from_status=finding.status,
            to_status=to_status,
            comment=comment,
            created_at=when,
        )
    )
    finding.status = to_status
    if to_status in ("resolved", "dismissed"):
        finding.resolved_at = when
        finding.resolved_by_id = actor.id
    db.flush()


def _upload(
    db: Session,
    inst: Institution,
    user: User,
    filename: str,
    rows: list[Row] | list[list[str]],
    days_ago: int,
    today: date,
) -> UploadBatch:
    batch = process_upload(
        db,
        institution=inst,
        uploaded_by_id=user.id,
        filename=filename,
        content=to_csv(rows),
        max_rows=10_000,
        today=today,
    )
    _backdate(db, batch, days_ago)
    return batch


def seed(db: Session, today: date | None = None) -> dict[str, object]:
    today = today or date.today()
    previous, current = demo_years(today)
    password_hash = hash_password(DEMO_PASSWORD)
    factory = RowFactory(2026)

    institutions: dict[str, Institution] = {}
    programmes: dict[tuple[str, str], Programme] = {}
    for spec in INSTITUTIONS:
        inst = Institution(
            code=spec.code, name=spec.name, state=spec.state, institution_type=spec.kind
        )
        db.add(inst)
        db.flush()
        institutions[spec.slug] = inst
        for p in spec.programmes:
            programme = Programme(
                institution_id=inst.id,
                code=p.code,
                name=p.name,
                level=p.level,
                duration_years=p.duration,
            )
            db.add(programme)
            db.flush()
            programmes[(spec.slug, p.code)] = programme
            for year in (previous, current):
                db.add(
                    IntakeConfiguration(
                        programme_id=programme.id,
                        academic_year=year,
                        approved_intake=p.intake,
                        supernumerary_seats=p.supernumerary,
                        source="synthetic-demo",
                        notes="Synthetic figure for demonstration; not an official approval.",
                    )
                )
    db.flush()

    users: dict[str, User] = {}

    def add_user(key: str, email: str, name: str, role: str, inst: Institution | None) -> None:
        user = User(
            email=email,
            full_name=name,
            role=role,
            password_hash=password_hash,
            institution_id=inst.id if inst else None,
        )
        db.add(user)
        users[key] = user

    for spec in INSTITUTIONS[:3]:
        inst = institutions[spec.slug]
        short = spec.name.split(" ")[0]
        add_user(
            f"{spec.slug}_operator",
            f"{spec.slug}.operator@demo.example",
            f"Data Operator — {short} (Demo)",
            "institution_operator",
            inst,
        )
        add_user(
            f"{spec.slug}_admin",
            f"{spec.slug}.admin@demo.example",
            f"Institution Admin — {short} (Demo)",
            "institution_admin",
            inst,
        )
    add_user(
        "central",
        "central.reviewer@demo.example",
        "Central Reviewer (Demo)",
        "central_reviewer",
        None,
    )
    add_user(
        "verifier",
        "verifier@demo.example",
        "Employer Verification Desk (Demo)",
        "authorized_verifier",
        None,
    )
    add_user(
        "sysadmin", "sysadmin@demo.example", "System Administrator (Demo)", "system_admin", None
    )
    db.flush()

    specs = {s.slug: s for s in INSTITUTIONS}
    aranya, kaveri, narmada = specs["aranya"], specs["kaveri"], specs["narmada"]
    p = {(s.slug, pr.code): pr for s in INSTITUTIONS for pr in s.programmes}
    py, cy = previous[2:4], current[2:4]

    # Aranya: previous year only. The current year is submitted live in the demo.
    rows = []
    for code, count, start in (
        ("BTECH-CSE", 58, 100001),
        ("BTECH-ECE", 52, 100101),
        ("BTECH-ME", 41, 100201),
        ("MTECH-DS", 15, 100301),
    ):
        prefix = f"AIT{py}{code.split('-')[1]}"
        rows += factory.rows(
            aranya,
            p[("aranya", code)],
            previous,
            count,
            start,
            prefix,
            supernumerary=1 if code == "BTECH-CSE" else 0,
        )
    _upload(
        db,
        institutions["aranya"],
        users["aranya_operator"],
        f"aranya-admissions-{previous}.csv",
        rows,
        380,
        today,
    )

    # Kaveri: both years. Previous year exceeded PGDM-GEN intake (resolved by central review).
    rows = []
    for code, count, start in (
        ("PGDM-GEN", 121, 200001),
        ("PGDM-FIN", 57, 200201),
        ("PGDM-BA", 44, 200301),
    ):
        rows += factory.rows(
            kaveri, p[("kaveri", code)], previous, count, start, f"KSM{py}{code.split('-')[1]}"
        )
    _upload(
        db,
        institutions["kaveri"],
        users["kaveri_operator"],
        f"kaveri-admissions-{previous}.csv",
        rows,
        375,
        today,
    )

    rows = []
    for code, count, start, extra in (
        ("PGDM-GEN", 112, 210001, 2),
        ("PGDM-FIN", 58, 210201, 0),
        ("PGDM-BA", 49, 210301, 3),
    ):
        rows += factory.rows(
            kaveri,
            p[("kaveri", code)],
            current,
            count,
            start,
            f"KSM{cy}{code.split('-')[1]}",
            supernumerary=extra,
        )
    conflict = rows[5]
    conflict.oci_status, conflict.nationality = "Y", "IN"  # OCI with Indian nationality
    _upload(
        db,
        institutions["kaveri"],
        users["kaveri_operator"],
        f"kaveri-admissions-{current}.csv",
        rows,
        20,
        today,
    )

    # Narmada: both years, plus a later correction file with a few rejected rows.
    rows = []
    for code, count, start in (
        ("BTECH-CSE", 55, 300001),
        ("BTECH-CIVIL", 36, 300101),
        ("DIP-ME", 26, 300201),
    ):
        rows += factory.rows(
            narmada, p[("narmada", code)], previous, count, start, f"NCE{py}{code.split('-')[1]}"
        )
    _upload(
        db,
        institutions["narmada"],
        users["narmada_operator"],
        f"narmada-admissions-{previous}.csv",
        rows,
        370,
        today,
    )

    rows = []
    for code, count, start in (
        ("BTECH-CSE", 57, 310001),
        ("BTECH-CIVIL", 38, 310101),
        ("DIP-ME", 27, 310201),
    ):
        rows += factory.rows(
            narmada, p[("narmada", code)], current, count, start, f"NCE{cy}{code.split('-')[1]}"
        )
    cross = rows[10]
    cross.apaar_id = CROSS_INSTITUTION_ID
    cross.full_name = "Ishaan Kulkarni"
    late = rows[70]
    late.admission_date = date(int(current[:4]) - 1, 12, 20).isoformat()  # outside window
    _upload(
        db,
        institutions["narmada"],
        users["narmada_operator"],
        f"narmada-admissions-{current}.csv",
        rows,
        12,
        today,
    )

    corrections = [rows[3], rows[4]]
    for row in corrections:
        row.enrolment_status = "WITHDRAWN"
    bad = [r.values() for r in rows[20:23]]
    for values in bad:
        values[6] = "31/02/2007"  # invalid date format
    _upload(
        db,
        institutions["narmada"],
        users["narmada_operator"],
        f"narmada-corrections-{current}.csv",
        [r.values() for r in corrections] + bad,
        6,
        today,
    )

    # Review history on a few findings.
    central, kaveri_admin = users["central"], users["kaveri_admin"]
    for finding in db.scalars(select(Finding)):
        if finding.rule_code == "INTAKE_EXCEEDED" and finding.academic_year == previous:
            _review(
                db,
                finding,
                central,
                "start_review",
                "in_review",
                "Requested approval documents from the institution.",
                360,
            )
            _review(
                db,
                finding,
                central,
                "resolve",
                "resolved",
                "Synthetic demo: additional-intake approval reference checked and recorded.",
                352,
            )
        elif finding.rule_code == "SUPERNUMERARY_EXCEEDED":
            _review(
                db,
                finding,
                kaveri_admin,
                "escalate",
                "escalated",
                "Third supernumerary admission was sanctioned late; escalating for central "
                "confirmation.",
                15,
            )
        elif (
            finding.rule_code == "CATEGORY_CONFLICT"
            and finding.institution_id == institutions["kaveri"].id
        ):
            _review(
                db,
                finding,
                kaveri_admin,
                "start_review",
                "in_review",
                "Checking the student's OCI card against admission documents.",
                14,
            )

    # Consent: most students recorded as consenting; some not recorded; a couple withdrawn.
    students = db.scalars(select(Student).order_by(Student.institution_student_id)).all()
    for index, student in enumerate(students):
        if index % 5 == 0:
            continue
        db.add(
            ConsentRecord(
                student_id=student.id,
                institution_id=student.institution_id,
                purpose=CONSENT_PURPOSE,
                status="granted",
                method="recorded_by_institution",
                note="Synthetic demo consent",
                created_at=utcnow() - timedelta(days=30),
            )
        )
        if index % 37 == 0:
            db.add(
                ConsentRecord(
                    student_id=student.id,
                    institution_id=student.institution_id,
                    purpose=CONSENT_PURPOSE,
                    status="withdrawn",
                    method="recorded_by_institution",
                    note="Student withdrew consent (synthetic)",
                    created_at=utcnow() - timedelta(days=3),
                )
            )
    db.flush()

    # A few issued record references for the Kaveri previous-year cohort.
    references = []
    kaveri_admissions = db.scalars(
        select(Admission)
        .where(
            Admission.institution_id == institutions["kaveri"].id,
            Admission.academic_year == previous,
        )
        .order_by(Admission.created_at)
        .limit(4)
    ).all()
    for admission in kaveri_admissions:
        record, _ = issue_record(db, admission, kaveri_admin.id)
        references.append(record.reference_code)

    db.add(
        AuditEvent(
            action="seed.loaded",
            outcome="success",
            details={
                "note": "Synthetic demo data loaded",
                "previous_year": previous,
                "current_year": current,
            },
        )
    )
    db.flush()
    return {
        "previous_year": previous,
        "current_year": current,
        "references": references,
        "students": len(students),
    }


def demo_upload_rows(db: Session, institution: Institution, today: date | None = None) -> bytes:
    """The live-demo upload for the current year, with deliberately planted problems.

    For Aranya it produces the scripted demo scenario (docs/demo-script.md). For any other
    institution it produces a small file with the same kinds of planted problems."""
    today = today or date.today()
    _, current = demo_years(today)
    factory = RowFactory(7)
    spec = next((s for s in INSTITUTIONS if s.code == institution.code), None)
    if spec is None:
        configured = db.scalars(
            select(Programme)
            .where(Programme.institution_id == institution.id)
            .order_by(Programme.code)
        ).all()
        if not configured:
            return to_csv([])
        spec = InstitutionSpec(
            institution.code,
            institution.name,
            institution.state,
            institution.institution_type,
            "custom",
            tuple(
                ProgrammeSpec(pr.code, pr.name, pr.level, pr.duration_years, 10, 0)
                for pr in configured
            ),
        )
    cy = current[2:4]
    tag = "".join(ch for ch in spec.code if ch.isdigit())[-1:] or "9"
    base = 400000 + int(tag) * 10000

    rows: list[Row] = []
    if spec.slug == "aranya":
        plan = (
            ("BTECH-CSE", 61, 2),
            ("BTECH-ECE", 47, 0),
            ("BTECH-ME", 33, 0),
            ("MTECH-DS", 17, 0),
        )
    else:
        plan = tuple((pr.code, 8, 0) for pr in spec.programmes[:2])
    short = {"aranya": "AIT", "kaveri": "KSM", "narmada": "NCE"}.get(spec.slug, "STU")
    offset = 0
    for code, count, extra in plan:
        programme = next(pr for pr in spec.programmes if pr.code == code)
        prefix = f"{short}{cy}{code.split('-')[-1]}"
        rows += factory.rows(
            spec, programme, current, count, base + offset, prefix, supernumerary=extra
        )
        offset += 100

    first_code = plan[0][0]
    first_programme = next(pr for pr in spec.programmes if pr.code == first_code)
    second_code = plan[1][0] if len(plan) > 1 else first_code

    def extra_row(sid: str, apaar: str, name: str, **changes: str) -> Row:
        admitted = factory.admission_date(current)
        row = Row(
            spec.code,
            first_code,
            current,
            sid,
            apaar,
            name,
            factory.dob(admitted, first_programme.level).isoformat(),
            "M",
            admitted.isoformat(),
        )
        for key, value in changes.items():
            setattr(row, key, value)
        return row

    # Accepted rows that raise findings.
    rows.append(extra_row(f"{short}{cy}X01", CROSS_INSTITUTION_ID, "Ishaan Kulkarni"))
    rows.append(
        extra_row(
            f"{short}{cy}X02",
            f"DEMO-APAAR-{base + 901:06d}",
            "Riya Menon",
            nri_category="Y",
            foreign_national_status="Y",
        )
    )
    twin = extra_row(f"{short}{cy}X03", f"DEMO-APAAR-{base + 902:06d}", "Kunal Bhat")
    rows.append(twin)
    rows.append(Row(**{**twin.__dict__, "programme_code": second_code}))
    rows.append(
        extra_row(
            f"{short}{cy}X04",
            f"DEMO-APAAR-{base + 903:06d}",
            "Tanvi Rao",
            date_of_birth=date(int(current[:4]) - 13, 1, 10).isoformat(),
        )
    )
    # Rejected rows.
    rows.append(extra_row(f"{short}{cy}X05", "", "Meera Joshi"))
    rows.append(extra_row(f"{short}{cy}X06", "DEMO-APAAR-12AB", "Arnav Shah"))
    rows.append(Row(**{**rows[3].__dict__}))  # exact duplicate of an earlier row
    rows.append(
        extra_row(
            f"{short}{cy}X07",
            f"DEMO-APAAR-{base + 904:06d}",
            "Divya Pillai",
            date_of_birth="14/03/2008",
        )
    )
    rows.append(
        extra_row(
            f"{short}{cy}X08",
            f"DEMO-APAAR-{base + 905:06d}",
            "Yash Gupta",
            programme_code="BTECH-AERO",
        )
    )
    rows.append(
        extra_row(
            f"{short}{cy}X09", f"DEMO-APAAR-{base + 906:06d}", "Navya Iyer", seat_type="MANAGEMENT"
        )
    )
    return to_csv(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load synthetic demo data")
    parser.add_argument("--reset", action="store_true", help="wipe all data first")
    args = parser.parse_args()
    if get_settings().app_env == "production":
        sys.exit("Refusing to seed demo data when APP_ENV=production")

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        if db.scalar(select(Institution.id).limit(1)) is not None:
            if not args.reset:
                sys.exit("Database already has data. Re-run with --reset to wipe and reseed.")
            _wipe(db)
        summary = seed(db)
        db.commit()
    print("Loaded synthetic demo data (DEMO DATA — NOT REAL STUDENT INFORMATION)")
    print(f"  Academic years: {summary['previous_year']} and {summary['current_year']}")
    print(f"  Students: {summary['students']}")
    print(f"  Demo password for all accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
