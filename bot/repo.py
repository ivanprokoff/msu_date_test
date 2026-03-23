import json
import aiosqlite
from dataclasses import dataclass
from typing import Optional, Any

PROFILE_REQUIRED_FIELDS = ("display_name", "gender", "age", "faculty_code", "about", "photo_file_id")

@dataclass
class Repo:
    db_path: str

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              tg_id INTEGER PRIMARY KEY,
              username TEXT,
              status TEXT NOT NULL DEFAULT 'NEW',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS verification_requests (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_tg_id INTEGER NOT NULL,
              student_card_file_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'PENDING',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              decided_by_admin_tg_id INTEGER,
              decided_at TEXT
            );

            CREATE TABLE IF NOT EXISTS profiles (
              user_tg_id INTEGER PRIMARY KEY,
              display_name TEXT,
              gender TEXT,               
              age INTEGER,
              faculty_code TEXT,
              interests_json TEXT,       
              about TEXT,
              photo_file_id TEXT,
              contact_username TEXT,
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_prefs (
              user_tg_id INTEGER PRIMARY KEY,
              looking_gender TEXT NOT NULL DEFAULT 'any', 
              age_min INTEGER NOT NULL DEFAULT 18,
              age_max INTEGER NOT NULL DEFAULT 35,
              faculties_json TEXT,
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS seen (
              viewer_tg_id INTEGER NOT NULL,
              shown_user_tg_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY(viewer_tg_id, shown_user_tg_id)
            );

            CREATE TABLE IF NOT EXISTS likes (
              from_tg_id INTEGER NOT NULL,
              to_tg_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY(from_tg_id, to_tg_id)
            );
            """)
            await db.commit()

    async def upsert_user(self, tg_id: int, username: Optional[str]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT INTO users(tg_id, username, status)
            VALUES(?, ?, 'NEW')
            ON CONFLICT(tg_id) DO UPDATE SET
              username=excluded.username,
              updated_at=datetime('now')
            """, (tg_id, username))
            await db.commit()

    async def user_status(self, tg_id: int) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT status FROM users WHERE tg_id=?", (tg_id,))
            row = await cur.fetchone()
            return row[0] if row else "NEW"

    async def submit_verification(self, tg_id: int, file_id: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET status='PENDING', updated_at=datetime('now') WHERE tg_id=?", (tg_id,))
            cur = await db.execute("""
            INSERT INTO verification_requests(user_tg_id, student_card_file_id, status)
            VALUES(?, ?, 'PENDING')
            """, (tg_id, file_id))
            await db.commit()
            return cur.lastrowid

    async def admin_pending(self) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
            SELECT vr.id, vr.user_tg_id, vr.student_card_file_id, u.username,
                   p.display_name, p.gender, p.age, p.faculty_code, p.about
            FROM verification_requests vr
            JOIN users u ON u.tg_id = vr.user_tg_id
            LEFT JOIN profiles p ON p.user_tg_id = vr.user_tg_id
            WHERE vr.status='PENDING'
            ORDER BY vr.id ASC
            LIMIT 1
            """)
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "request_id": row[0], "user_tg_id": row[1], "student_card_file_id": row[2],
                "username": row[3], "display_name": row[4], "gender": row[5],
                "age": row[6], "faculty_code": row[7], "about": row[8]
            }

    async def admin_decide(self, request_id: int, admin_tg_id: int, decision: str) -> int:
        new_user_status = "VERIFIED" if decision == "APPROVED" else "REJECTED"
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT user_tg_id FROM verification_requests WHERE id=? AND status='PENDING'", (request_id,))
            row = await cur.fetchone()
            if not row: return 0
            user_tg_id = row[0]

            await db.execute("UPDATE verification_requests SET status=?, decided_by_admin_tg_id=?, decided_at=datetime('now') WHERE id=?", (decision, admin_tg_id, request_id))
            await db.execute("UPDATE users SET status=?, updated_at=datetime('now') WHERE tg_id=?", (new_user_status, user_tg_id))
            await db.commit()
            return user_tg_id

    async def profile_upsert(self, tg_id: int, **fields) -> None:
        interests = fields.pop("interests", None)
        interests_json = json.dumps(interests, ensure_ascii=False) if interests is not None else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO profiles(user_tg_id) VALUES(?) ON CONFLICT(user_tg_id) DO NOTHING", (tg_id,))
            for key, value in fields.items():
                if value is None: continue
                await db.execute(f"UPDATE profiles SET {key}=?, updated_at=datetime('now') WHERE user_tg_id=?", (value, tg_id))
            if interests_json is not None:
                await db.execute("UPDATE profiles SET interests_json=?, updated_at=datetime('now') WHERE user_tg_id=?", (interests_json, tg_id))
            await db.commit()

    async def profile_update_field(self, tg_id: int, field: str, value: Any) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            if field == "interests":
                val = json.dumps(value, ensure_ascii=False)
                await db.execute("UPDATE profiles SET interests_json=?, updated_at=datetime('now') WHERE user_tg_id=?", (val, tg_id))
            else:
                await db.execute(f"UPDATE profiles SET {field}=?, updated_at=datetime('now') WHERE user_tg_id=?", (value, tg_id))
            await db.commit()

    async def profile_get(self, tg_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT user_tg_id, display_name, gender, age, faculty_code, interests_json, about, photo_file_id, contact_username FROM profiles WHERE user_tg_id=?", (tg_id,))
            row = await cur.fetchone()
            if not row: return None
            return {
                "tg_id": row[0], "display_name": row[1], "gender": row[2],
                "age": row[3], "faculty_code": row[4], "interests": json.loads(row[5]) if row[5] else [],
                "about": row[6], "photo_file_id": row[7], "contact_username": row[8],
            }

    async def prefs_set(self, tg_id: int, looking_gender: str, age_min: int, age_max: int, faculties: list[str]) -> None:
        faculties_json = json.dumps(faculties, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT INTO search_prefs(user_tg_id, looking_gender, age_min, age_max, faculties_json)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(user_tg_id) DO UPDATE SET
              looking_gender=excluded.looking_gender, age_min=excluded.age_min,
              age_max=excluded.age_max, faculties_json=excluded.faculties_json, updated_at=datetime('now')
            """, (tg_id, looking_gender, age_min, age_max, faculties_json))
            await db.commit()

    async def prefs_get(self, tg_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT looking_gender, age_min, age_max, faculties_json FROM search_prefs WHERE user_tg_id=?", (tg_id,))
            row = await cur.fetchone()
            if not row: return {"looking_gender": "any", "age_min": 18, "age_max": 35, "faculties": []}
            return {
                "looking_gender": row[0], "age_min": int(row[1]),
                "age_max": int(row[2]), "faculties": json.loads(row[3]) if row[3] else [],
            }

    async def reset_seen(self, viewer_tg_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM seen WHERE viewer_tg_id=?", (viewer_tg_id,))
            await db.commit()

    async def mark_seen(self, viewer_tg_id: int, shown_user_tg_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO seen(viewer_tg_id, shown_user_tg_id) VALUES(?, ?)", (viewer_tg_id, shown_user_tg_id))
            await db.commit()

    async def like(self, from_tg_id: int, to_tg_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO likes(from_tg_id, to_tg_id) VALUES(?, ?)", (from_tg_id, to_tg_id))
            await db.commit()
            cur = await db.execute("SELECT 1 FROM likes WHERE from_tg_id=? AND to_tg_id=? LIMIT 1", (to_tg_id, from_tg_id))
            return (await cur.fetchone()) is not None

    async def contact_for(self, tg_id: int) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT contact_username FROM profiles WHERE user_tg_id=?", (tg_id,))
            row = await cur.fetchone()
            if row and row[0]: return row[0]
            cur = await db.execute("SELECT username FROM users WHERE tg_id=?", (tg_id,))
            row = await cur.fetchone()
            return f"@{row[0]}" if row and row[0] else None

    async def search_next(
            self,
            viewer_tg_id: int,
            looking_gender: str,
            age_min: int,
            age_max: int,
            faculties: list[str],
    ) -> Optional[dict]:
        params = [viewer_tg_id, viewer_tg_id, age_min, age_max]

        gender_sql = ""
        if looking_gender in ("male", "female"):
            gender_sql = "AND p.gender = ?"
            params.append(looking_gender)

        faculty_sql = ""
        if faculties:
            placeholders = ",".join("?" for _ in faculties)
            faculty_sql = f"AND p.faculty_code IN ({placeholders})"
            params.extend(faculties)

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(f"""
            SELECT
              p.user_tg_id, p.display_name, p.gender, p.age, p.faculty_code,
              p.interests_json, p.about, p.photo_file_id, p.contact_username
            FROM profiles p
            JOIN users u ON u.tg_id = p.user_tg_id
            LEFT JOIN seen s ON s.viewer_tg_id = ? AND s.shown_user_tg_id = p.user_tg_id
            WHERE
              u.status='VERIFIED'
              AND p.user_tg_id != ?
              AND s.shown_user_tg_id IS NULL
              AND p.display_name IS NOT NULL AND TRIM(p.display_name) != ''
              AND p.gender IN ('male','female')
              AND p.age BETWEEN ? AND ?
              AND p.faculty_code IS NOT NULL AND TRIM(p.faculty_code) != ''
              AND p.about IS NOT NULL AND TRIM(p.about) != ''
              AND p.photo_file_id IS NOT NULL AND TRIM(p.photo_file_id) != ''
              {gender_sql}
              {faculty_sql}
            ORDER BY random()
            LIMIT 1
            """, params)
            row = await cur.fetchone()
            if not row:
                return None

            return {
                "tg_id": row[0],
                "display_name": row[1],
                "gender": row[2],
                "age": row[3],
                "faculty_code": row[4],
                "interests": json.loads(row[5]) if row[5] else [],
                "about": row[6],
                "photo_file_id": row[7],
                "contact_username": row[8],
            }