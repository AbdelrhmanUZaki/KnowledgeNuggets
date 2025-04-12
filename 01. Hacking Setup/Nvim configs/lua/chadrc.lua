-- This file needs to have same structure as nvconfig.lua
-- https://github.com/NvChad/ui/blob/v3.0/lua/nvconfig.lua
-- Please read that file to know all available options :(
require "custom"
---@class ChadrcConfig
local M = {}

M.base46 = {
  theme = "catppuccin",
  -- transparency = true,

  hl_override = {
    ["@comment"] = { italic = true },
  },
}

return M
