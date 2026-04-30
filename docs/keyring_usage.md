# What is Keyring
keyring is a utility for creating and managing keystores on local machine.

# What are keystores
keystores are encrypted files used to store secrets (eg: passwords, api keys, etc) in encrypted form in local machine.

# Setup
install:
    ```
    sudo apt install -y gnome-keyring python3-pip dbus-x11
    pip3 install -U keyring keyrings.alt
    ```

configure for non-gui (ie: wsl):
    Option A using keyrings.alt
        ```export KEYRING_BACKEND=keyrings.alt.file.EncryptedKeyring```
        
        Add this export into ~/.bashrc to make it permanent.
    
    Option B using gnome-keyring
        ```
        if [ -z "$GNOME_KEYRING_CONTROL" ]; then
            eval $(dbus-launch --sh-syntax)
            eval $(echo "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null)
            export GNOME_KEYRING_CONTROL
        fi
        ```

        Add this to ~/.bashrc.

store secrets:
    Using Google App Password as an example.
    1. Generate a Gmail App Password.
        Your regular Gmail password won't work for programs trying to send email via Gmail programmatically.
        Go to your Google Account > Security > App Passwords. Create an app named and generate a 16-character password.
    2. Use ```keyring set XXXX YYYY``` to store the password.
        A password prompt will come up. Type the 16-character password in and press enter.

# Retrieve and use secrets
    ```python
    import keyring
    import smtplib
    import ssl
    from email.message import EmailMessage

    # Retrieve secret
    secret = keyring.get_password("XXXX", "YYYY") # Retrieves securely

    if secret:
        # Email Setup
        msg = EmailMessage()
        msg.set_content("This is an automated email from WSL2!")
        msg['Subject'] = "Automated Email"
        msg['From'] = "your_email@gmail.com"
        msg['To'] = "recipient@example.com"

        # Send Email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(user, secret)
            server.send_message(msg)
            print("Email sent successfully!")
    ```

# Some notes

## Authentication password
When 1st time accessing keyring, either to store, retrieve, or delete secrets, a system prompt will appear asking for an authenication password.
To make things easy for yourself, use the same password as your computer login.

After you set this, sometimes this system prompt will come up again as your access keyring. You can then just type in your password and continue accessing keyring.

## Deleting keyring
There may come a time when you need to delete keyring, maybe you forgot the authenticating password. Maybe there are now too many old/unused keystores.

Simply use ```rm ~/.local/share/keyrings/*```. Then exit wsl via ```wsl.exe --shutdown```.

Wait some minutes and then log back into wsl. Then try to access keyring via 1 of its commands. The system prompt will appear asking you to set your authentication password, just as if you are using it for the 1st time. Back in business!