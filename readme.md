# Distributor Deployment

This repository contains the deployment assets, docker-compose configuration and helper scripts used to install and run the Distributor application on a VPS host.

Once You Puchase our application we will do the installation process for you. Incase you want to do it yourself, follow the `Self Installation Guide` below.

## Prerequisites

1. VPS hosting

You can buy VPS hosting from any provider. Our minimum recommendation for production is:

- 1 vCPU core
- 4 GB RAM
- 50 GB NVMe disk
- 4 TB bandwidth (or suitable for your expected traffic)
- OS: a recent Ubuntu LTS (recommended), Choose from `Plain Os`

If you want a quick option, you can use Hostinger (referral). Click the badge below to open the referral link:

[![Hostinger - Get VPS](https://img.shields.io/badge/Hostinger-Get%20VPS-blue?style=for-the-badge&logo=hostinger)](https://www.hostinger.com/cart?product=vps%3Avps_kvm_1&period=12&referral_type=cart_link&REFERRALCODE=ZVZANGREDOFQ&referral_id=019a68e1-7338-71b1-b03f-2ebcb6ae13e5)

2. A domain name

3. DNS pointed to your VPS public IP


## Self Installation Guide

### 1. Clone Repository
Clone this repository on your target VPS:
```bash
git clone https://github.com/xitoss/distributor-deployment.git
cd distributor-deployment
```
### 2. Setup License
The application requires two license files in the `license/` folder:
- `license_public.pem` (already included)
- `license.pem` (you will create this from the provided license file)

When you purchased this product, we sent you a license file (e.g., `company_license.pem` or `license.pem`). This file contains your company information and looks like this:
```json
{
  "payload": {
    "company": "Your company name",
    "domain": "Your domain name",
    "issued": "datetime of issuance",
    "plan": "plan name",
    "email" : "your company email"
  },
  "signature": "__a long signature string__"
}
```

⚠️ **Important**: Do not modify any of the license contents!

To install your license:

1. On your local computer:
   - Open the license file we sent you using Notepad or any text editor
   - Select everything (Ctrl+A) and copy it (Ctrl+C)

2. On your VPS server:
   ```bash
   # View the current template content (optional)
   cat license/_license.pem
   ```
   This file will be completely blank. Paste the license contents  you copied here.

   When pasting your license content, make sure to:
   - Include all the content (the entire JSON with payload and signature)
   - Keep all quotes and brackets exactly as they are
   - Right-click to paste in most terminal applications

3. Rename the file:
   ```bash
   mv license/_license.pem license/license.pem
   ```
   This removes the underscore (_) from the filename.

### 3. Create Virtual Environment
Setting up a virtual environment is recommended for a clean and stable installation.

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

You'll see `(venv)` in your shell prompt when the virtual environment is active.

### 4. Run Preflight Setup
The preflight script will create a `.env` file containing all necessary configuration. This file is critical for the application - please do not edit it manually unless you know what you're doing.

Run the preflight script:
```bash
python scripts/preflight.py
```

The script will ask for the following information:

1. **Main Domain**
   - Enter your domain without 'www' (e.g., if your site is www.example.com, enter `example.com`)
   - default `domain` from the license file

2. **Let's Encrypt Email**
   - Provide a valid email address for SSL certificate notifications
   - SSL renewal and security notifications will be sent to this address
   - default `email` from the license file

3. **Database Credentials**
   - Username (default: `distributor`)
   - Password (default: `generated from license file`)
   - ⚠️ Use a strong password in production!

4. **Admin (Superuser) Account**
   - Username (default: from license or `admin`)
   - Email (default: from license or `admin@example.com`)
   - Password (default: `generated from license file`)
   - ⚠️ Change the default password after first login!

The script will generate additional secure values automatically:
- Secret keys for Django
- Agent communication keys
- Allowed hosts configuration
- Database connection settings

If you make a mistake, you can run the preflight script again to start over.


### 5. Deploy the Application
Once you have your license and `.env` file ready, deploy the application:

```bash
docker compose up -d --build
```

The deployment process will:
1. Pull the application image
2. Set up the database
3. Initialize the agent service
4. Install and configure Nginx
5. Set up SSL certificates
6. Create your superuser account
7. Set up static files

This may take several minutes. Once complete, you can access:
- Main site: `https://www.yourdomain.com`
- Admin panel: `https://yourdomain.com/staff_panel`

### Next Steps
1. Log in to the staff panel using your superuser credentials
2. Complete your company setup
3. Create employee accounts
4. Configure your company

For detailed instructions on using the application, please refer to the user manual available in the staff panel.

### Troubleshooting
- If the deployment fails, check the Docker logs:
  ```bash
  docker compose logs -f
  ```
- Ensure your domain's DNS is properly configured before deploying
- Make sure ports 80 and 443 are open on your firewall
- For additional help, refer to our support documentation or contact our support team

### Deactivating Virtual Environment
When you're done with the installation, you can deactivate the virtual environment:
```bash
deactivate
```