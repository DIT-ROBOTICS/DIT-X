# docker buildx bake -f docker/docker-bake.hcl [target]
# Normally driven by `ditx image` / CI, which set the variables below.

variable "REGISTRY"   { default = "ghcr.io/seanchangx" }
variable "TAG"        { default = "local" }
variable "ROS_DISTRO" { default = "humble" }
variable "PLATFORMS"  { default = "linux/amd64" }
# space separated, filled from ditx.repos by `ditx image`
variable "DOMAINS"    { default = "main navigation localization vision" }
# extra tags, space separated (e.g. "stable sha-1a2b3c4")
variable "EXTRA_TAGS" { default = "" }

function "tags" {
  params = [name]
  result = concat(
    ["${REGISTRY}/${name}:${TAG}"],
    [for t in compact(split(" ", EXTRA_TAGS)) : "${REGISTRY}/${name}:${t}"])
}

target "_common" {
  context    = "."
  dockerfile = "docker/Dockerfile"
  platforms  = split(",", PLATFORMS)
  args       = { ROS_DISTRO = ROS_DISTRO }
}

group "default" {
  targets = ["base", "dev", "cross", "runtime"]
}

target "base" {
  inherits = ["_common"]
  target   = "base"
  tags     = tags("eurobot-base")
}

target "dev" {
  inherits = ["_common"]
  target   = "dev"
  tags     = tags("eurobot-dev")
}

# arm64 cross compile environment; only built for (and used on) amd64 machines
target "cross" {
  inherits  = ["_common"]
  target    = "cross"
  platforms = ["linux/amd64"]
  tags      = tags("eurobot-cross")
}

target "runtime" {
  name     = "runtime-${d}"
  matrix   = { d = compact(split(" ", DOMAINS)) }
  inherits = ["_common"]
  target   = "runtime"
  args     = { ROS_DISTRO = ROS_DISTRO, DOMAIN = d }
  tags     = tags("eurobot-${d}")
}
