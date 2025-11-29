{ pkgs ? import <nixpkgs> {} } :

pkgs.mkShell {
  packages = with pkgs; [ neofetch lolcat packwiz python314 neo-cowsay ];
  shellHook = ''
    echo "Welcome to LunarFox git repository. There are some useful scripts in ./scripts. Use packwiz command in ./versions/<mod_loader>/<mc_version> to manager modpack." | cowsay | lolcat 
  '';
}
