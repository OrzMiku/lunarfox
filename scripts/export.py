from utils import (
    get_all_versions,
    export_modpacks,
)


def main():
    versions = get_all_versions()
    for mod_loader in versions:
        export_modpacks(versions[mod_loader], format="modrinth")


if __name__ == "__main__":
    main()
