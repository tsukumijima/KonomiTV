{
  pkgs,
#   buildNpmPackage,
}:

pkgs.stdenv.mkDerivation rec {
  pname = "konomitv-client";
  version = "unstable";

  src = ./.;
  logosSrc = ../server/static/logos;
  packageJSON = ./package.json;
  nativeBuildInputs = with pkgs; [
    nodejs-slim
    yarn
    prefetch-yarn-deps
    yarnConfigHook
    yarnBuildHook
  ];

  offlineCache = pkgs.fetchYarnDeps {
    yarnLock = "${src}/yarn.lock";
    hash = "sha256-7HQBSU6eMy3UFUkw3kLK/LfLyYrRMLdOzBnLeDbs7yk=";
  };
  buildPhase = ''
    export HOME=$(mktemp -d)
    rm -fr dist
    cp -r ${logosSrc} logos
    node logoGenerator.js
    yarn --offline build
  '';
  installPhase = ''
    runHook preInstall
    mv dist $out
    runHook postInstall
  '';
}
