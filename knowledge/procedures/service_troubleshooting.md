# Linux Service Troubleshooting Procedure

When a system service is not working correctly, follow these steps.

Step 1: Check the status of the service.
Before anything else, we must determine if the service is running, stopped or crashed.

Use:
systemctl status <service_name>

Review the output and identify whether the service is active, inactive, or failed.

Step 2: Review service logs.

Use:

journalctl -u <service_name> 

Look for errors, warnings, and startup failures.

Step 3: Verify configuration files.

Check configuration files for syntax errors or invalid settings.

Step 4: Verify network connectivity.

Ensure the server can reach required dependencies and services.
You can check if the service is listening on the correct port:
sudo ss -tulpn | grep <service_name>

Step 5: Restart the service.
Once you have corrected any configuration issues or freed up port resources, you can attempt a clean restart.

Use:

sudo systemctl restart <service_name>

Then verify the service status again.

Safety Note: Always run systemctl status <service_name> again shortly after restarting to ensure the service remains active and does not crash after a few seconds.

Step 6: Escalation.

If the issue cannot be resolved, gather logs and diagnostic information before escalating to the system administrator.

Use:
echo "=== STATUS ===" && systemctl status <service_name> && echo "=== LOGS ===" && journalctl -u <service_name> -n 100 --no-pager

Save this output and share it with the senior engineering team