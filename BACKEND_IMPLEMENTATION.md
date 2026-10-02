# Backend Implementation

How the backend in this repo implements [SPEC.md](SPEC.md), and everything the frontend needs to call it.

## 1. Overview

A Flask JSON API for a to-do app that can import Canvas assignments as tasks.

- Stack: Flask, Flask-SQLAlchemy + psycopg 3, Render Postgres, gunicorn on Render.
- Base URL: the Render service URL, e.g. `https://<service>.onrender.com`. All paths below are relative to it.
- Users sign in with a Canvas personal access token (PAT) once, then use a session token.

## 2. Conventions

- **Bodies** are JSON (`Content-Type: application/json`). Responses are JSON unless the status is `204` (no body).
- **Auth:** every endpoint except `POST /auth/token` and `GET /health` needs `Authorization: Bearer <session_token>`.
- **Datetimes** are ISO 8601 strings, returned in UTC (e.g. `2026-10-01T03:59:59+00:00`). Datetimes sent without a timezone are treated as UTC.
- **Ids** are this app's integer ids, never Canvas ids. A task's `course_id` is the `id` from `GET /canvas/courses`.
- **Bulk only:** tasks, courses and assignments are changed through list endpoints. A bulk request is all-or-nothing: if any item is invalid or any id isn't yours, nothing is changed.
- Unknown fields in request bodies are ignored.

## 3. Data shapes

**User**
```json
{ "canvas_user_id": 145824, "name": "Jane Doe", "canvas_connected": true }
```
`canvas_connected` is `false` when no usable PAT is stored, so the frontend should ask for a new one.

**Task**
```json
{
  "id": 7,
  "title": "Homework 3",
  "description": "",
  "due_at": "2026-10-01T03:59:59+00:00",
  "completed": false,
  "recurrence": "none",
  "course_id": 2,
  "html_url": "https://canvas.cmu.edu/courses/123/assignments/456"
}
```

| Field | Type | Client can set | Notes |
|---|---|---|---|
| `title` | string | yes | Required on create. Trimmed; can't be blank. |
| `description` | string | yes | Defaults to `""`. |
| `due_at` | datetime or null | yes | Defaults to `null`. |
| `completed` | bool | yes | Defaults to `false`. |
| `recurrence` | `none` \| `daily` \| `weekly` \| `monthly` | yes | Defaults to `none`. Anything but `none` needs a `due_at`. |
| `course_id` | int or null | yes | Must be one of your courses. Manual tasks may use any course. |
| `html_url` | string or null | no | Canvas assignment link. `null` for manual tasks. |

A task is **Canvas-imported** when `html_url` is not null.

**Course**
```json
{ "id": 2, "name": "Cell Biology", "status": "kept" }
```

**Assignment**
```json
{
  "id": 5,
  "course_id": 2,
  "name": "Homework 3",
  "due_at": "2026-10-01T03:59:59+00:00",
  "html_url": "https://canvas.cmu.edu/courses/123/assignments/456",
  "status": "pending"
}
```

`status` on courses and assignments is one of:
- `pending`: seen on Canvas, the user hasn't chosen yet.
- `kept`: courses have their assignments synced; assignments have a task.
- `ignored`: skipped by sync.

## 4. Endpoints

### Auth

| Method & path | Body | Success | Notes |
|---|---|---|---|
| `POST /auth/token` | `{ "canvas_token": "<PAT>" }` | `200` `{ session_token, expires_at, user: User }` | No auth header. `401` if Canvas rejects the PAT. Replaces any stored PAT. |
| `GET /auth/me` | none | `200` User | |
| `POST /auth/logout` | none | `204` | Ends this session only. |
| `DELETE /auth/canvas` | none | `204` | Deletes the stored PAT and **all** sessions. Tasks, courses and choices are kept. |
| `DELETE /auth/account` | none | `204` | Deletes the user and all their data. Can't be undone. |

### Tasks

| Method & path | Body / query | Success | Notes |
|---|---|---|---|
| `GET /tasks` | optional `?course_id=<id>` or `?course_id=none` | `200` `[Task]` | Sorted by `due_at` (nulls last), then `id`. `none` means tasks with no course. |
| `POST /tasks` | `[{ title, description?, due_at?, completed?, recurrence?, course_id? }]` | `201` `[Task]` | Create one task by sending a list of one. |
| `PATCH /tasks` | `[{ id, ...fields to change }]` | `200` `[Task]` in request order | Only the fields you send change. |
| `DELETE /tasks` | `{ "ids": [1, 2] }` | `204` | Deleting a Canvas-imported task marks its assignment `ignored`. |

### Canvas

| Method & path | Body | Success | Notes |
|---|---|---|---|
| `POST /canvas/sync` | none | `200` `{ pending_courses: [Course], pending_assignments: [Assignment] }` | Pulls from Canvas. Can be slow. |
| `GET /canvas/courses` | none | `200` `[Course]` | All known courses, any status. |
| `GET /canvas/assignments` | none | `200` `[Assignment]` | All known assignments, any status. |
| `PATCH /canvas/courses` | `[{ id, status: "kept" \| "ignored" }]` | `200` `[Course]` | Assignments of a newly kept course show up on the **next** sync. |
| `PATCH /canvas/assignments` | `[{ id, status: "kept" \| "ignored" }]` | `200` `[Assignment]` | Keeping an assignment creates its task **right away**. |

### Other

| Method & path | Success | Notes |
|---|---|---|
| `GET /health` | `200` `{ "status": "ok" }` | No auth. Useful for waking a sleeping service. |

## 5. Errors

Errors look like `{ "error": "<message>" }`. The message is readable enough to show to users.

| Status | Meaning | Frontend should |
|---|---|---|
| `400` | Malformed body or invalid field | Show the message. |
| `401` | Missing, invalid or expired session, or a rejected PAT at `POST /auth/token` | Send the user to the login screen. |
| `403` with `"error": "canvas_token_required"` | Stored PAT is missing, expired, revoked or unreadable. The backend has already deleted it. The session is still valid. | Ask for a new PAT and send it to `POST /auth/token`. |
| `404` | An id doesn't exist or isn't yours | Refresh local data. |
| `502` | Canvas couldn't be reached | Retry later. |

This is `403` instead of `401` on purpose: `401` means "log in again", while `canvas_token_required` means "the session is fine, just provide a new PAT". Only `/canvas/*` endpoints return it. The body also has a `message` field.

## 6. Frontend flows

**Login**
1. The user pastes a PAT, created under Canvas → Account → Settings → New Access Token.
2. `POST /auth/token`, then keep `session_token` in memory or `sessionStorage`. Never store the PAT.
3. Send `Authorization: Bearer <session_token>` on every request.

**Import from Canvas**
1. `POST /canvas/sync` returns `pending_courses`.
2. The user picks courses, then `PATCH /canvas/courses`.
3. `POST /canvas/sync` again. Now `pending_assignments` lists the pending assignments in kept courses.
4. The user picks assignments, then `PATCH /canvas/assignments`. Kept ones become tasks immediately.
5. Later syncs return only new items, plus anything the user hasn't decided on yet.

**Completing a repeating task:** `PATCH /tasks` with `{ id, completed: true }`. The response has `completed: false` and `due_at` moved forward one interval, so render the response rather than assuming it's done.

**Settings**
- To un-ignore, list with `GET /canvas/courses` or `GET /canvas/assignments` and `PATCH` the status back to `kept`.
- Log out with `POST /auth/logout`.
- Disconnect Canvas with `DELETE /auth/canvas`. Remind the user to also delete the PAT in Canvas, because the backend can't revoke it.
- Delete the account with `DELETE /auth/account`, after a confirmation dialog.

**Cold start:** the free Render service sleeps after 15 minutes idle, and the first request can take about a minute. Show a loading state. Optionally ping `GET /health` on page load.

## 7. Behavior and design choices

**Sync**
- Courses come from active enrollments (`GET /api/v1/courses?enrollment_state=active&include[]=term`). Courses Canvas hides because of their access dates are skipped.
- Assignments are fetched only for kept courses that are active this term, one call per course with `Link` pagination.
- For assignments that already have a task, re-sync overwrites the task's `due_at` and `course_id` with Canvas's values. `title`, `description`, `completed` and `recurrence` are left alone. The link always comes from the assignment.
- Courses or assignments that disappear from Canvas are kept as they are.
- Imported tasks start with an empty `description`, because Canvas descriptions are raw HTML.

**Ignoring**
- Ignoring a course keeps its existing tasks, but they stop getting re-sync updates.
- Ignoring an assignment through `PATCH /canvas/assignments` also keeps its task.
- Deleting a Canvas-imported task marks its assignment `ignored`, so sync won't offer it again. Un-ignoring it (setting `kept`) re-creates the task.
- Statuses can't be set back to `pending`.

**Recurrence**
- Completing a repeating task moves `due_at` forward one interval (day, week or month) and sets `completed` back to `false`. It moves one interval even if the task is several intervals overdue.
- Monthly repeats clamp to the end of the month: Jan 31 goes to Feb 28, then to Mar 28.
- A repeating Canvas task gets its `due_at` reset to Canvas's value on the next sync.

**Sessions**
- Sessions last a fixed 7 days from login and aren't extended by activity.
- They're opaque random tokens rather than JWTs, so logout and disconnect take effect immediately.

**API shape**
- There are no single-task endpoints (`/tasks/<id>`). The bulk endpoints cover one item as a list of one, and `GET /tasks` already returns everything.

## 8. Security

- **PATs** are encrypted with Fernet using `ENCRYPTION_KEY`, which exists only as an environment variable. PATs are never returned or logged. Canvas calls go server-to-server.
- **Session tokens** are 32 random bytes (`secrets.token_urlsafe`). Only their SHA-256 hash is stored.
- **Identity:** the Canvas user id comes only from Canvas's `/users/self` response, never from the request.
- **Scoping:** every query filters by the logged-in user. Other users' ids return `404`, the same as ids that don't exist.
- **CORS** allows only `FRONTEND_URL`. If it's unset, no cross-origin requests are allowed. No cookies are used.

## 9. Configuration and deployment

| Env var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres URL. Use the Internal URL on Render and the External URL locally. `postgresql://` is rewritten to `postgresql+psycopg://` automatically. |
| `ENCRYPTION_KEY` | Fernet key. Changing it makes stored PATs unreadable, so users get `canvas_token_required` and have to resubmit. |
| `FRONTEND_URL` | Scheme and host only, e.g. `https://<username>.github.io`. |

- **Start command:** `gunicorn app:app`. The build installs `requirements.txt`.
- **Tables** are created at startup with `db.create_all()`. There are no migrations, so schema changes to existing tables must be applied by hand or by recreating the database.
- **Local development:** put the variables in `.env`. `app.py` loads it with python-dotenv only if python-dotenv is installed. It's deliberately left out of `requirements.txt`. Run with `python app.py` (port 8080).

## 10. Code layout

| File | Responsibility |
|---|---|
| `app.py` | App setup, CORS, blueprints, `create_all`, JSON error handlers |
| `models.py` | Tables: `User`, `Session`, `Course`, `Assignment`, `Task`; status constants |
| `security.py` | PAT encryption, session creation and hashing, `authenticate` |
| `canvas_client.py` | Canvas REST calls, pagination, `CanvasAuthError` on 401 |
| `recurrence.py` | Next due date for daily, weekly and monthly |
| `api_helpers.py` | Bulk body parsing; loading the user's own rows or returning 404 |
| `routes/auth.py` | `/auth/*` |
| `routes/tasks.py` | `/tasks` |
| `routes/canvas.py` | `/canvas/*`, including the `canvas_token_required` handler |

## 11. Known limitations

- **Logging back in needs a PAT.** A PAT is the only login credential, so after logging out or after a session expires (7 days) the user must paste a PAT again. That can be the same one or a new one, and their data is still restored. The stored PAT is only used while the user has a valid session.
- Free Render Postgres expires 30 days after creation, with a 14-day grace period.
- Free web services have cold starts; see [section 6](#6-frontend-flows).
- Expired session rows are never cleaned up. They're rejected but stay in the database.
- Check CMU's Canvas policy on sharing PATs with third-party apps before real users sign up.
