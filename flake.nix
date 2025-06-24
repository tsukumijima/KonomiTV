{
  description = "KonomiTV - Flake with separate client/server builds";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix.url = "github:nix-community/poetry2nix";

  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      poetry2nix,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        inherit (nixpkgs) lib;
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            # poetry2nix.overlays.default
            # (self: super: rec {
            #   python3 = super.python3.override {
            #     packageOverrides = (
            #       self: super: {
            #         inherit (super.python3.pkgs) ;
            #         fastapi-cli = super.fastapi-cli.overridePythonAttrs {
            #           dependencies = [
            #             super.rich-toolkit
            #             super.typer
            #             super.uvicorn
            #           ] ++ super.uvicorn.optional-dependencies.standard;

            #           optional-dependencies = {
            #             standard = [
            #               super.uvicorn
            #             ] ++ super.uvicorn.optional-dependencies.standard;
            #           };
            #         };
            #       }
            #     );
            #   };
            # })
          ];
        };
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
        konomitv-client = import ./client/package.nix { inherit pkgs; };
        konomitv-server = mkPoetryApplication { projectDir = ./server/.; };

      in
      {
        packages = {
          inherit konomitv-client konomitv-server;
          default = konomitv-server;
        };

        # devShells.default = pkgs.mkShell {
        #   buildInputs = [
        #     pkgs.nodejs
        #     pkgs.python3
        #     pkgs.poetry
        #   ];
        # };
      }
    );
}
