return {
  "jose-elias-alvarez/null-ls.nvim",
  event = "BufRead",
  config = function()
    local null_ls = require "null-ls"

    null_ls.setup {
      sources = {
        null_ls.builtins.diagnostics.vale,
      },
    }
  end,
}
