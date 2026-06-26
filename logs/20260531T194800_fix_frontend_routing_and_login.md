# Fix Frontend Routing and Login Redirect

## Changes

### `frontend/src/pages/LoginPage.vue`
- Fixed post-login redirect from `/classify` (old route) to `/tasks`

### `frontend/src/pages/TaskSelectionPage.vue`
- Added `@click.stop="selectTask(task)"` to Start button so click propagates to selectTask handler

### `frontend/index.html`
- Changed `<title>` from "semANT title annotation" to "Image Rater"

## Result
- Login redirects correctly to `/tasks`
- Start button on task cards navigates to `/compare/:taskId` or `/rate/:taskId`
- Page title reflects the new application name
- All pages tested end-to-end: login → task selection → comparison page, leaderboard, admin CRUD
