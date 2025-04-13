return {
  "stevearc/conform.nvim",
  event = "BufRead",
  config = function()
    require("conform").setup {
      notify_on_error = true,
      format_on_save = {
        lsp_format = "fallback",
        timeout_ms = 500,
      },

      formatters_by_ft = {
        tex = { "latexindent", "bibtex-tidy" }, -- Assuming you want to format LaTeX files as well
        html = { "prettier" },
        css = { "prettier" },
        markdown = { "prettier" },
        json = { "prettier" },
        yaml = { "yq" },
        lua = { "stylua" },
        -- python = { "isort", "black" },
        python = { "isort" },
        sh = { "shfmt" },
        javascript = { "prettier" },
        -- Use the "*" filetype to run formatters on all filetypes.
        ["*"] = { "codespell" },
        -- Use the "_" filetype to run formatters on filetypes that don't
        -- have other formatters configured.
        ["_"] = { "trim_whitespace" },
      },
    }
  end,
}
