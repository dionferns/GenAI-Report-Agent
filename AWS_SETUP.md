# Complete AWS Setup Guide — From Zero to Configured

> Step-by-step guide to set up AWS CLI and configure your AWS account for Bedrock.

---

## Part 1: Create AWS Account (If You Don't Have One)

### Step 1: Go to AWS Console

Visit: https://aws.amazon.com/

### Step 2: Click "Create an AWS Account"

- Enter your email address
- Enter a password (make it strong!)
- Enter AWS account name (can be anything, e.g., "my-interview-demo")
- Click "Continue"

### Step 3: Add Contact Information

- Full name
- Address
- City, State/Province, Postal Code
- Country
- Phone number
- Click "Continue"

### Step 4: Add Payment Method

- Credit/Debit card information
- AWS charges for services used (but App Runner + Bedrock have reasonable costs)

### Step 5: Verify Phone Number

- AWS will call or text a verification code
- Enter the code
- Click "Continue"

### Step 6: Select Support Plan

- Choose **"Basic Plan"** (free)
- Click "Complete sign up"

### Step 7: Confirm Email

- Check your email for AWS confirmation
- Click the verification link

**Done!** You now have an AWS account. 🎉

---

## Part 2: Install AWS CLI

### macOS (Using Homebrew)

**Option A: Homebrew (Easiest)**

```bash
brew install awscli
```

Verify installation:
```bash
aws --version
# Output: aws-cli/2.x.x ...
```

**Option B: Direct Download**

1. Download: https://awscli.amazonaws.com/AWSCLIV2.pkg
2. Double-click the installer
3. Follow the prompts
4. Verify: `aws --version`

### macOS (Using pip)

If you have Python installed:

```bash
pip install awscli
```

Verify:
```bash
aws --version
```

### Linux

```bash
# Using apt (Ubuntu/Debian)
sudo apt update
sudo apt install awscli

# Using yum (Amazon Linux/RHEL)
sudo yum install awscli

# Verify
aws --version
```

### Windows

**Option A: Installer**

1. Download: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run the installer
3. Follow prompts
4. Verify in PowerShell: `aws --version`

**Option B: pip (if Python installed)**

```powershell
pip install awscli
aws --version
```

---

## Part 3: Create AWS Access Keys

### Why Access Keys?

Access keys let your local machine authenticate with AWS without entering your password every time. There are two parts:
- **Access Key ID** (like username)
- **Secret Access Key** (like password)

### Step 1: Go to IAM Console

1. Log in to AWS Console: https://console.aws.amazon.com/
2. In the top right, click your account name
3. Click **"Security credentials"**

### Step 2: Create Access Key

1. Scroll down to **"Access keys"** section
2. Click **"Create access key"**
3. Choose use case: **"Command Line Interface (CLI)"**
4. Check the confirmation box
5. Click **"Next"**

### Step 3: Add Description (Optional)

- Description: "GenAI Report Agent Demo" (or anything)
- Click **"Create access key"**

### Step 4: Save Your Keys (IMPORTANT!)

You'll see a screen with:
- **Access Key ID** (starts with AKIA...)
- **Secret Access Key** (long string)

**⚠️ SAVE THESE SECURELY:**

**Option A: Copy to Secure Location**
- Save in a password manager (1Password, LastPass, etc.)
- Or write down on paper and keep in a safe place
- **Do NOT share or commit to GitHub**

**Option B: Download CSV**
- Click **"Download .csv file"** — this is your only chance!
- Keep this file somewhere safe

### Step 5: Finish

Click **"Done"**

---

## Part 4: Configure AWS CLI Locally

### Method 1: Interactive Configuration (Recommended)

Run this command:

```bash
aws configure
```

You'll be prompted for:

```
AWS Access Key ID [None]: AKIA...paste your access key ID here...
AWS Secret Access Key [None]: paste your secret access key here...
Default region name [None]: eu-west-2
Default output format [None]: json
```

**Explanation:**
- **Access Key ID**: Paste the AKIA... value from Part 3
- **Secret Access Key**: Paste the long secret key from Part 3
- **Region**: `eu-west-2` (London region, where gov.uk data is)
- **Output format**: `json` (structured output)

Press Enter after each to confirm.

**Verify it worked:**

```bash
aws sts get-caller-identity
```

You should see output like:
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

If you see this, ✅ AWS CLI is configured correctly!

### Method 2: Environment Variables (Alternative)

If you prefer not to store credentials locally:

```bash
# Set these in your shell (macOS/Linux)
export AWS_ACCESS_KEY_ID=AKIA...your_access_key...
export AWS_SECRET_ACCESS_KEY=...your_secret_key...
export AWS_DEFAULT_REGION=eu-west-2

# Verify
aws sts get-caller-identity
```

**Pros:** Credentials only in memory, not on disk
**Cons:** Need to set them every terminal session

### Method 3: .env File (For Project)

In your project directory, you can set them in `.env`:

```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...your_secret...
AWS_DEFAULT_REGION=eu-west-2
```

Then load in your shell:

```bash
source .env
aws sts get-caller-identity
```

**Note:** `.env` is git-ignored, so it won't be committed.

---

## Part 5: Verify AWS CLI is Working

### Test 1: Check Your Identity

```bash
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

### Test 2: List Available Regions

```bash
aws ec2 describe-regions --region-name eu-west-2
```

**Expected output:**
```
REGIONS with eu-west-2 listed
```

### Test 3: List S3 Buckets (if any)

```bash
aws s3 ls
```

**Expected output:**
```
(If no buckets, you'll see empty output — that's OK!)
```

**All three working?** ✅ AWS CLI is configured!

---

## Part 6: Request Bedrock Model Access

Now that AWS CLI is working, request access to the Claude model.

### Option A: AWS Console (Visual, Recommended)

1. Go to AWS Console: https://console.aws.amazon.com/
2. Search for **"Bedrock"** in the search bar
3. Click **"Bedrock"**
4. Click **"Model access"** (left sidebar, bottom)
5. Click **"Manage model access"**
6. Find **"Anthropic"** section
7. Check the box next to **"Claude 3.5 Sonnet"** (or latest Claude version)
8. Click **"Save changes"** (bottom right)

**Wait 5-10 minutes** for approval.

### Option B: AWS CLI

```bash
# This will request access programmatically
# (Less intuitive, but works)

aws bedrock list-foundation-models \
  --region eu-west-2
```

### Verify Approval

After 5-10 minutes, check if approved:

```bash
aws bedrock list-foundation-models \
  --region eu-west-2 \
  | grep -i "claude-3-5-sonnet"
```

**You should see:**
```
anthropic.claude-3-5-sonnet-20241022-v2:0
```

If you see it, ✅ Bedrock access approved!

If not, wait a bit longer and try again.

---

## Part 7: Test Bedrock Access

### Option A: Using AWS CLI

```bash
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --region eu-west-2 \
  --body '{
    "anthropic_version": "bedrock-2023-06-01",
    "max_tokens": 100,
    "messages": [
      {
        "role": "user",
        "content": "Say OK"
      }
    ]
  }' \
  response.json

cat response.json
```

**Expected output:**
```json
{
  "content": [
    {
      "text": "OK"
    }
  ],
  ...
}
```

### Option B: Using Python (In Your Project)

```bash
source .venv/bin/activate
python test_simple.py
```

**Expected output:**
```
✅ Imports
✅ Configuration
✅ Database
✅ Vector Store
✅ LLM (Bedrock)
```

All passing? ✅ Bedrock is working!

---

## Part 8: Configure Your Project

### Step 1: Create .env File

```bash
cd /Users/dionfernandes/Projects/GenAI-Report-Agent
cp .env.example .env
```

### Step 2: Edit .env

```bash
nano .env
```

Set the following values:

```env
# LLM Provider
LLM_PROVIDER=bedrock

# AWS Configuration
AWS_ACCESS_KEY_ID=AKIA...paste_your_key_here...
AWS_SECRET_ACCESS_KEY=...paste_your_secret_here...
AWS_DEFAULT_REGION=eu-west-2

# LangSmith (optional, but recommended for observability)
LANGCHAIN_API_KEY=...if_you_have_one...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=data-reply-genai-agent

# Storage (local for now)
CHROMA_PERSIST_DIR=./data/chroma
SQLITE_DB_PATH=./data/archive.db
LOG_FILE=./logs/agent.log

# Agent Configuration
DEFAULT_TOPIC=uk_ai_regulation
INGEST_INTERVAL_MINUTES=60
MAX_URLS_PER_RUN=15
MAX_CRITIC_ITERATIONS=2
```

**Save:** Press `Ctrl+O`, then `Enter`, then `Ctrl+X`

### Step 3: Test Configuration

```bash
source .venv/bin/activate
python test_simple.py
```

**All tests passing?** ✅ You're ready!

---

## Part 9: Quick Reference — AWS CLI Commands

### Identity & Account

```bash
# Check your AWS identity
aws sts get-caller-identity

# List users
aws iam list-users

# List access keys
aws iam list-access-keys
```

### Bedrock

```bash
# List available models
aws bedrock list-foundation-models --region eu-west-2

# Test Bedrock connection
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --region eu-west-2 \
  --body '{"anthropic_version":"bedrock-2023-06-01","max_tokens":10,"messages":[{"role":"user","content":"OK"}]}' \
  /dev/stdout | python -m json.tool
```

### App Runner (for later deployment)

```bash
# List services
aws apprunner list-services --region eu-west-2

# Describe a service
aws apprunner describe-service \
  --service-arn arn:aws:apprunner:eu-west-2:123456789012:service/genai-report-agent

# Start deployment
aws apprunner start-deployment \
  --service-arn arn:aws:apprunner:eu-west-2:123456789012:service/genai-report-agent
```

### Logs & Monitoring

```bash
# List CloudWatch logs
aws logs describe-log-groups --region eu-west-2

# View log stream
aws logs tail /ecs/genai-report-agent --follow --region eu-west-2
```

---

## Troubleshooting

### "command not found: aws"

AWS CLI not installed. See Part 2.

```bash
# Verify installation
aws --version

# If not found, reinstall:
brew install awscli  # macOS
# or
sudo apt install awscli  # Linux
```

### "Unable to locate credentials"

AWS CLI is installed but not configured. See Part 4.

```bash
aws configure  # Then enter your credentials
```

### "InvalidSignatureException"

Access keys are incorrect or expired.

```bash
# Check your keys
aws iam list-access-keys

# If old, delete and create new ones (Part 3)
```

### "An error occurred (UnauthorizedOperation)"

Your AWS user doesn't have permission. Check IAM role.

```bash
# Check your permissions
aws iam get-user

# May need to add Bedrock permissions in IAM console
```

### "Model access not approved yet"

You haven't requested Bedrock access yet, or approval is still pending.

```bash
# Check status
aws bedrock list-foundation-models --region eu-west-2 | grep claude

# If not showing, go to AWS console and request access (Part 6)
```

### "InvalidParameterException: Invalid model identifier"

Model not available in your region or not approved.

```bash
# List available models in your region
aws bedrock list-foundation-models --region eu-west-2

# If claude-3-5-sonnet not showing, request access in console
```

---

## Security Best Practices

### ✅ DO:

- ✅ Use strong passwords for AWS account
- ✅ Keep access keys in `.env` (git-ignored)
- ✅ Use AWS IAM roles (not root account) for CLI
- ✅ Rotate access keys every 90 days
- ✅ Use MFA (Multi-Factor Authentication) for extra security

### ❌ DON'T:

- ❌ Commit access keys to GitHub
- ❌ Share access keys in Slack/email
- ❌ Use root account AWS credentials (create IAM user instead)
- ❌ Keep access keys in plain text files outside `.env`
- ❌ Use the same access keys across multiple projects

---

## Next Steps

Once you've completed this guide:

1. ✅ AWS CLI installed
2. ✅ Access keys created
3. ✅ AWS CLI configured
4. ✅ Bedrock access requested and approved
5. ✅ `.env` configured
6. ✅ `python test_simple.py` all passing

**Then follow:** BEDROCK_QUICKSTART.md to deploy to AWS App Runner

---

## Cost Tracking

After setting up, check your AWS costs:

1. Go to: https://console.aws.amazon.com/costmanagement
2. Click **"Dashboards"** → **"Cost and usage"**
3. You can see:
   - Bedrock charges (by model calls)
   - App Runner charges (by vCPU-hours)
   - Data transfer costs

For this demo:
- **Bedrock:** ~$0.01-0.10 per ingestion run (depends on article size)
- **App Runner:** ~$40/month if kept running (pause to save costs)

---

## Summary Checklist

- [ ] AWS account created
- [ ] AWS CLI installed (`aws --version` works)
- [ ] Access keys created in IAM
- [ ] AWS CLI configured (`aws configure`)
- [ ] Identity verified (`aws sts get-caller-identity` works)
- [ ] Bedrock model access requested
- [ ] Bedrock model access approved (check with `aws bedrock list-foundation-models`)
- [ ] `.env` file created with credentials
- [ ] Project tests passing (`python test_simple.py` all ✅)

**All checked?** 🎉 You're ready to deploy!

---

## Resources

- [AWS Getting Started](https://aws.amazon.com/getting-started/)
- [AWS CLI User Guide](https://docs.aws.amazon.com/cli/)
- [Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS Free Tier](https://aws.amazon.com/free/)

---

## Need Help?

**AWS CLI not working?**
- Check: `aws --version`
- Reinstall if needed

**Credentials not working?**
- Verify: `aws sts get-caller-identity`
- Check keys are correct in `.env`

**Bedrock not approved?**
- Go to AWS console
- Request model access manually
- Wait 5-10 minutes

**Still stuck?**
- Read the official AWS docs linked above
- Check AWS support forums

Good luck! 🚀

