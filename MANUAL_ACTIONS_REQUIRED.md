# LEEWU AI — REQUIRED MANUAL ACTIONS PRIOR TO PUBLIC RELEASE

**Classification:** STRICT USER APPROVAL REQUIRED  
**Policy:** Antigravity has performed all safe local remediations. External actions, Git history rewriting, credential revocations, and remote pushes require explicit user execution.

---

## 1. CREDENTIAL ROTATION (MANDATORY & CRITICAL)

The Telegram bot token and Nebius API key present in historical commit `a35acae` must be considered compromised.

### Step 1.1: Revoke & Reissue Telegram Bot Token
1. Open Telegram and message **`@BotFather`**.
2. Send `/mybots` and select your LeeWu AI bot (`@Leewubot` or designated bot).
3. Select **API Token** ➡️ **Revoke current token**.
4. Copy the new token and update your local `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN="<new_revoked_token>"
   ```

### Step 1.2: Revoke & Reissue Nebius API Key
1. Log in to the **Nebius Token Factory Console** (`https://tokenfactory.nebius.com`).
2. Navigate to **Service Accounts / API Keys**.
3. Identify the key with ID `[REDACTED_NEBIUS_KEY]` and delete / revoke it.
4. Generate a new API Key with appropriate inference scopes.
5. Update your local `.env` file:
   ```env
   NEBIUS_API_KEY="<new_nebius_key>"
   ```

---

## 2. GIT HISTORY CLEANUP (MANDATORY BEFORE PUSH)

To purge the exposed commit (`a35acae`) and historical CSV filepaths (`6ec8a6f`) from Git history:

A safe, automated script has been prepared outside the repository:
`C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\scratch\git_history_cleanup_plan\run_git_history_cleanup.ps1`

### Execution Procedure:
1. Open PowerShell in `youtube/scratch/git_history_cleanup_plan/`.
2. Inspect the script to verify backup creation:
   ```powershell
   Get-Content run_git_history_cleanup.ps1
   ```
3. Run the script with explicit execution switch:
   ```powershell
   .\run_git_history_cleanup.ps1 -Execute
   ```
4. Verify that a complete timestamped backup directory is created.

---

## 3. PUBLIC GIT PUSH (UPON CONFIRMING ROTATION & CLEANUP)

Once the local history is clean and new credentials are in place:

```bash
cd C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\LeeWuAiDevpostnVidia
git status
# Confirm working tree is clean and 0 sensitive files are staged
git remote -v
# Push to authorized submission repository
git push origin main --force
```

---

## 4. DEVPOST SUBMISSION FINALIZATION

1. Open Devpost submission dashboard for Nebius × NVIDIA Hackathon.
2. Paste the public GitHub repository URL.
3. Paste the YouTube 3-minute demo video link.
4. Confirm Track selection: *Autonomous Agents / Enterprise AI*.
5. Submit project prior to the deadline.
