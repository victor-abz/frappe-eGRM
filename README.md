### egrm

Electronic Grievance redress Mechanism

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app egrm
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/egrm
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

### Production deployment notes

#### Raising the maximum upload size (Android APK, attachments)

The default nginx and Frappe limits reject the mobile-app APK upload (~80 MB). Raise both to the same ceiling on every production host:

1. **nginx** — edit the bench-generated source, NOT the deployed file. `/etc/nginx/conf.d/frappe-bench.conf` is a symlink that points back to it. Editing the symlink target with `sed -i` would otherwise replace the symlink with a regular file, drifting the deployed copy from the bench source.

    ```bash
    # Find and edit the bench-managed source
    sudo sed -i 's/client_max_body_size 50m;/client_max_body_size 200m;/' \
      /home/frappeuser/frappe-bench/config/nginx.conf

    # If the symlink at /etc/nginx/conf.d/frappe-bench.conf was previously replaced
    # with a regular file (because someone ran sed -i on it directly), restore it:
    sudo rm /etc/nginx/conf.d/frappe-bench.conf
    sudo ln -s /home/frappeuser/frappe-bench/config/nginx.conf \
      /etc/nginx/conf.d/frappe-bench.conf

    # Validate + reload (no downtime)
    sudo nginx -t && sudo systemctl reload nginx
    ```

2. **Frappe** — the app-level limit is enforced separately via `max_file_size` in `common_site_config.json` (bytes, default 26214400 / 25 MB):

    ```bash
    cd /home/frappeuser/frappe-bench
    bench config set-common-config -c max_file_size 209715200   # 200 MB
    bench restart
    ```

Verify with a HEAD probe after the change:

```bash
curl -I https://egrm.example.org/files/<some-apk>.apk
# expect 200 + Content-Length matching the file
```


### License

mit
