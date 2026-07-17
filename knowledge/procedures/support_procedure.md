
# Standard Support Procedures

This document outlines the standard operational procedures for common administrative tasks, including user management, secure access configuration, and database maintanance.

## Procedure 1: Adding a New User to a Server
To grant access to a new team member or system administration, follow these steps in order

### Step 1.1: Create the User Account
Generate a new user with a secure home directory:

sudo adduser <username>

### Step 1.2: Grant Administrative(Sudo) Privileges

If the user requires admin rights, add them to the sudo group:

sudo usermod - aG sudo <username>

### Step 1.3 Set Up Passwordless SSH Access
We strictly forbid password authentication in production. All users must connect via SSH keys.

Switch to the newly created user:
su - <username>

Create the secure SSH directory and set correct permissions:

mkdir -p ~/.ssh && chmod 700 ~/.ssh

Create the authorized keys file:

touch ~/.ssh/suthorized_keys && chmod 600 ~/.ssh/authorized_keys

Append the user's public SSH key ( usually id_rsa.pub or id_ed25519.pub) into ~/.ssh/authorized_keys .

## Procedure 2: Safe Package Updated

To maintain system security, packages must be updated regularly. Follow this zero-downtime routine:

### Step 2.1 Update Package Lists

Fetch the latest verion of package lists from the repositories:

sudo apt update

### Step 2.2 List Upgradable Packages
Review what is about to change before executing the upgrade:

apt list --upgradable

### Step 2.3 Apply Safe Upgrades

Apple updates that do not require removing existing packages or installing new ones:

sudo apt upgrade -y
