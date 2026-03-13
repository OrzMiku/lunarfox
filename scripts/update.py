from utils import (
    get_all_versions,
    update_modpacks,
)


def main():
    versions = get_all_versions()
    for mod_loader in versions:
        update_modpacks(versions[mod_loader])


if __name__ == "__main__":
    main()
