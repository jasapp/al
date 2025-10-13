# Notion Setup Guide for Al

Al stores all data in Notion databases so you can view and manage everything visually. If Notion is offline, Al automatically falls back to local JSON files.

## Step 1: Create Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **"+ New integration"**
3. Name it: **"Al Supply Chain Manager"**
4. Select your workspace
5. Set capabilities:
   - ✅ Read content
   - ✅ Update content
   - ✅ Insert content
6. Click **"Submit"**
7. Copy the **Internal Integration Token** (starts with `secret_`)

## Step 2: Create Notion Databases

Create these 4 databases in your Notion workspace:

### 1. Vendors Database

**Properties:**
- `Name` (Title) - Vendor company name
- `Contact` (Text) - Contact person name
- `Email` (Email) - Contact email
- `Phone` (Phone) - Contact phone number
- `Products` (Multi-select) - Products they supply
- `Lead Time (days)` (Number) - Typical lead time
- `Notes` (Text) - Additional notes

### 2. Scrap History Database

**Properties:**
- `Product` (Title) - Product that was scrapped
- `Quantity` (Number) - Number of units scrapped
- `Reason` (Text) - Why it was scrapped
- `Date` (Date) - When it was scrapped
- `Material Cost` (Number) - Estimated material cost lost
- `Time Lost (min)` (Number) - Machine time wasted
- `Materials Lost` (Text) - Breakdown of materials wasted

### 3. Invoices Database

**Properties:**
- `Invoice Number` (Title) - Invoice/order number
- `Vendor` (Text) - Vendor name
- `Total Amount` (Number) - Total invoice amount
- `Order Date` (Date) - When order was placed
- `Processed Date` (Date) - When Al processed it

### 4. Inventory Alerts Database (Optional)

**Properties:**
- `Component` (Title) - Component name
- `Current Level` (Number) - Current quantity
- `Reorder Point` (Number) - When to reorder
- `Status` (Select: Low, Critical, Out of Stock)
- `Last Warned` (Date) - When Al last warned
- `Snoozed Until` (Date) - If user asked to wait
- `Vendor` (Text) - Preferred vendor

## Step 3: Share Databases with Integration

For each database:
1. Open the database in Notion
2. Click **"..."** (top right)
3. Click **"+ Add connections"**
4. Select **"Al Supply Chain Manager"**
5. Click **"Confirm"**

## Step 4: Get Database IDs

For each database:
1. Open the database as a full page
2. Copy the URL - it looks like:
   ```
   https://www.notion.so/your-workspace/DATABASE_ID?v=...
   ```
3. The `DATABASE_ID` is the 32-character string between the last `/` and the `?`
   - Example: `a1b2c3d4e5f67890a1b2c3d4e5f67890`

## Step 5: Configure Al

Add these to your `.env` file:

```bash
# Notion Integration
NOTION_API_KEY=secret_your_integration_token_here
NOTION_VENDORS_DB_ID=your_vendors_database_id
NOTION_SCRAP_DB_ID=your_scrap_database_id
NOTION_INVOICES_DB_ID=your_invoices_database_id
NOTION_ALERTS_DB_ID=your_alerts_database_id  # Optional
```

## Step 6: Restart Al

```bash
./stop.sh
./start.sh
```

Check the logs to verify Notion connection:
```bash
tail -f logs/al.log
```

You should see: `Notion integration initialized successfully`

## Usage

Once configured, Al will automatically:
- ✅ Store vendors in Notion when you send invoices
- ✅ Log scrap entries to Notion
- ✅ Track invoice duplicates in Notion
- ✅ Fall back to local JSON if Notion is offline

You can view and edit all data directly in Notion!

## Troubleshooting

**"Notion not available" in logs:**
- Check your `NOTION_API_KEY` is correct
- Verify the integration is active at https://www.notion.so/my-integrations

**"Could not create page in database":**
- Make sure you shared the database with the integration (Step 3)
- Verify the database ID is correct

**Data only in JSON files:**
- Check your database IDs match the database URLs
- Ensure database properties match the schema above

## Local Fallback

If Notion is unavailable, Al uses these local files:
- `.al_vendors.json` - Vendor data
- `.al_scrap_history.json` - Scrap history
- `.al_invoices.json` - Invoice tracking

Al will automatically sync back to Notion when it comes online.
