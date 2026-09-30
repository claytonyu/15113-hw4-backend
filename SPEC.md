# SPEC: Canvas-Integrated To-Do List App

## Overview
A to-do list web app should have users sign in, manage their own tasks, and sync assignments from Canvas as tasks.

## Architecture
- Frontend: Web-app. (separately hosted on GitHub Pages, calls the backend API). Do not work on this part, we are only working on the backend here.
- Backend: Python w/ Flask API, deployed on Render with gunicorn.
- Database: Render Postgres, set up through the Render web dashboard.
  - Setup: Dashboard → New → Postgres. Free plan, **same region as the web service**.
  - Copy the database's **Internal Database URL** into the web service's Environment tab as `DATABASE_URL`. The internal URL only works from inside Render, which is what we want.
  - Use the **External Database URL** only for local development or for inspecting data with `psql` or a GUI client. Render's dashboard doesn't have a table browser.
  - Flask connects through SQLAlchemy (Flask-SQLAlchemy + `psycopg`). Tables get created at app startup with `db.create_all()`, since free web services have no shell or pre-deploy command for running migrations.
  - Free Render Postgres expires 30 days after creation, with a 14-day grace period before deletion. Expect to recreate it, or upgrade, if the app has to last longer.

## Coding Style
You are a senior software architect. Strictly adhere to these principles:
1. KISS (Keep It Simple, Stupid): Write straightforward, uncomplicated logic. Avoid premature optimizations or speculative "what-if" abstractions.
2. YAGNI (You Aren't Gonna Need It): Do not add extra features, utility methods, or error-handling blocks for scenarios that cannot physically happen in this scope.
3. SOLID: Ensure conceptual single responsibility per class/function.
4. Reduce cognitive complexity (aim for low cyclomatic complexity).

## Specifications

### 1. Users & Authentication
Users authenticate with a Canvas **personal access token (PAT)**. The frontend tells users how to create one (Canvas → Account → Settings → New Access Token). The Canvas user id, not the PAT, is the backend's method to identify users, so all of a user's data is retained across different PATs for the same Canvas account.

**Login flow:**
1. User pastes their PAT into the frontend, which sends it once to `POST /auth/token` with `{canvas_token}`.
2. Backend validates the PAT by calling Canvas `GET /api/v1/users/self`. If Canvas rejects it, return 401.
3. Backend takes the Canvas user id **only from that Canvas response** (never from the request body), then creates the user or finds their existing record.
4. Backend stores the PAT encrypted, replacing any previously stored PAT for that user.
5. Backend returns a **session token**. The frontend never stores or re-sends the PAT.
6. Frontend keeps the session token in memory or `sessionStorage` and sends it as `Authorization: Bearer <token>` on every request.

**Why not send the PAT on every request:** a PAT grants full access to the student's Canvas account (submitting work, messaging, reading grades) and often never expires. Keeping it only on the backend limits the damage if the frontend is compromised.

**Why bearer tokens instead of cookies:** GitHub Pages (`*.github.io`) and Render (`*.onrender.com`) are different sites. Safari blocks cross-site cookies and Chrome restricts them, so cookie sessions would fail for many users.

**Session tokens:** 32 random bytes (`secrets.token_urlsafe`), stored as a SHA-256 hash, expire after 7 days. These are opaque tokens rather than JWTs so logout can revoke them immediately.

**Logout vs. disconnect:**
- **Log out** ends the current session only. The stored PAT and all user data stay, so logging in again doesn't need a new PAT. (Canvas shows a PAT only once at creation, so most users couldn't re-enter the old one.)
- **Disconnect Canvas** deletes the stored PAT and all of the user's sessions. All tasks, courses and ignore decisions stay. Submitting a new PAT for the same Canvas account restores access to them.
- Deleting the PAT from the backend does **not** revoke it in Canvas. The frontend should tell users to delete it under Canvas → Account → Settings.

**Expired or revoked PATs:** users can set an expiry on a PAT or delete it in Canvas. If a Canvas call returns 401, the backend deletes the stored PAT and returns an error telling the frontend to ask for a new one, instead of failing the sync silently.

**Auth endpoints:**
- `POST /auth/token`: PAT → session token.
- `GET /auth/me`: current user (Canvas id, name).
- `POST /auth/logout`: deletes the current session.
- `DELETE /auth/canvas`: deletes the stored PAT and all of the user's sessions. User data is kept.
- `DELETE /auth/account`: deletes the user and all of their data (tasks, courses, assignments, PAT, sessions).

### 2. To-Do Features & Endpoints for Front-End
- The main unit: **a task**. It should have the following fields: a title, description, a due date, status (completed or not), and recurrence.
  - Recurrence is a `recurrence` field: `none` | `daily` | `weekly` | `monthly`. Completing a repeating task moves its due date forward by one interval and resets it to not completed.
  - For canvas-imported assignments, have a field which identifies the particular Canvas course (for categorization), and a field which directly links to the canvas assignment link.
- Allow for Creating, Updating, and Deleting individual and groups of tasks.
  - Deleting a Canvas-imported task marks its assignment as ignored, so the next sync doesn't prompt for it again.
- Allow for reading tasks
  - All tasks at once.
  - Also allow for reading only tasks in particular Canvas course (or no Canvas course, using the sentinel `?course_id=none`).
- Allow for manually-created tasks on this app to be associated with a Canvas course (even if not present in the actual Canvas course.)

### 3. Canvas Integration
Each Canvas assignment is able to be ported over to a task on this app. The user should have freedom to decide which assignments to port over.
From the database, the backend will have either known or not known about certain classes and assignments on Canvas. The process of dealing with unknown classes & assignments will be called "importing" here.
On sync, search for all classes in the current term.
- "Current term" means active enrollments: `GET /api/v1/courses?enrollment_state=active&include[]=term`. Students can't query Canvas terms directly.
- When importing new classes, allow the front-end user to choose which classes to keep and which classes to ignore. This information should be stored in the database.
Then for all unignored classes, check its assignments.
- For importing new assignments, allow the user to choose which assignments to keep on this application, and which to ignore. This information should also be stored in the database.
- Each unignored assignment should have the information listed above in section 2.
- Assignments are fetched with the Canvas REST API, one call per unignored course: `GET /api/v1/courses/:course_id/assignments?per_page=100`, following `Link` header pagination.

**Re-sync:** for assignments already imported as tasks, sync updates the Canvas-sourced fields (due date, assignment link, course). User edits to title and description are left alone.

**Un-ignoring:** the user can change ignore decisions for classes and assignments later (from the settings page). Un-ignoring an assignment creates its task.

### 4. Database
The Database should store each user's Canvas id for identification, their encrypted PAT (nullable, empty after disconnecting), and their hashed session tokens.
For each user, it should also store its known classes and whether or not they were ignored. It should also store known assignments, and whether or not they were ignored. It should also store the information about each task (as listed in section 2).

### 5. Frontend User Workflow (do not implement, but for reference)
- The user will log in by pasting a Canvas PAT, with instructions on how to create one.
- Login, task list, task detail/edit, settings (log out, disconnect Canvas with a reminder to revoke the PAT in Canvas, delete account, un-ignore classes/assignments)

### 6. Security
This is very important. Make sure to check this after making any changes regarding security.
- API Keys and PATs should be safe. They should be encrypted in whatever database is used.
  - PATs are encrypted with Fernet (`cryptography` package) using `ENCRYPTION_KEY`, which is stored only as a Render env var and never in the database.
  - PATs are never returned to the frontend or written to logs.
  - Session tokens are stored only as hashes.
- The Canvas user id always comes from Canvas's `/users/self` response, never from client input.
- Users can only access their own data
- CORS restricted to the frontend's URL (TBD)

### 7. Deployment & Config
- Hosting: frontend on GitHub Pages, backend on Render.
- Environment variables (set in the Render dashboard):
  - `DATABASE_URL`: Render Postgres internal URL
  - `ENCRYPTION_KEY`: Fernet key for PATs. Losing or changing it makes stored PATs unreadable, so users would need to submit new ones.
  - `CANVAS_BASE_URL`: e.g. `https://canvas.cmu.edu`
  - `FRONTEND_URL`: e.g. `https://<username>.github.io`, used for CORS. The CORS origin is scheme + host only, with no path.

## Open Issues
- **School policy:** some institutions restrict sharing Canvas PATs with third-party apps. Check CMU's Canvas policy before real users submit tokens.
- **Cold starts:** free Render services sleep after 15 minutes idle, so the first request (including login) can take about a minute.
- Write tests 