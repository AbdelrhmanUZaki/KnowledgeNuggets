-- EXAMPLE
local on_attach = require("nvchad.configs.lspconfig").on_attach
local on_init = require("nvchad.configs.lspconfig").on_init
local capabilities = require("nvchad.configs.lspconfig").capabilities

local lspconfig = require "lspconfig"

local servers = {
  "lua_ls",
  "html",
  "pylsp",
  "cssls",
  -- "pyright",
  "bashls",
  "intelephense",
  "texlab",
}

-- lsps with default config
for _, lsp in ipairs(servers) do
  lspconfig[lsp].setup {
    on_attach = on_attach,
    on_init = on_init,
    capabilities = capabilities,
  }
end

lspconfig.lua_ls.setup {
  settings = {
    Lua = {
      diagnostics = {
        globals = { "vim" },
      },
    },
  },
}

-- Configure python-lsp-server for Neovim LSP
lspconfig.pylsp.setup {
  -- Enable or disable diagnostics
  -- To enable the diagnostics, you may need to have a linter installed, such as pylint.
  -- cmd = { 'pylsp', '--log-file', '/tmp/pylsp.log' },  -- If not set, pylsp will be searched in $PATH, and pylsp will use its default command.
  on_attach = on_attach,
  settings = {
    pylsp = {
      plugins = {
        rope = { enabled = true }, -- Rope for Completions and renaming
        pyflakes = { enabled = true }, -- Pyflakes linter to detect various errors
        mccabe = { enabled = true }, -- McCabe linter for complexity checking
        pycodestyle = { enabled = true }, -- Pycodestyle linter for style checking
        pydocstyle = { enabled = true }, -- Pydocstyle linter for docstring style checking (disabled by default)
        -- autopep8 = {enabled = true},    -- Autopep8 for code formatting
        yapf = { enabled = true }, -- YAPF for code formatting (preferred over autopep8)
        flake8 = { enabled = true }, -- Flake8 for error checking (disabled by default)
        pylint = { enabled = true }, -- Pylint for code linting (disabled by default)
      },
    },
  },
}

-- texlab specific configuration

-- lspconfig.texlab.setup {
--   on_attach = on_attach,
--   on_init = on_init,
--   capabilities = capabilities,
--   settings = {
--     texlab = {
--       build = {
--         executable = "latexmk",
--         args = { "-pdf", "-interaction=nonstopmode", "-synctex=1", "%f" },
--         onSave = true,
--       },
--       forwardSearch = {
--         executable = "zathura",
--         args = { "--synctex-forward", "%l:1:%f", "%p" },
--       },
--       lint = {
--         onChange = true,
--       },
--     },
--   },
-- }

-- -- texlab specific configuration without forwardSearch and build settings
-- lspconfig.texlab.setup {
--   on_attach = on_attach,
--   on_init = on_init,
--   capabilities = capabilities,
--   settings = {
--     texlab = {
--       lint = {
--         onChange = true,
--       },
--     },
--   },
-- }

-- -- Create a function to trigger forward search
-- local function sync_zathura()
--   local params = vim.lsp.util.make_position_params()
--   vim.lsp.buf_request(0, "textDocument/forwardSearch", params, function(err, _, result, _, _)
--     if err then
--       print("Error during forward search: ", err)
--     end
--   end)
-- end
--
-- -- Set up an autocommand to trigger the forward search on save
-- vim.api.nvim_create_autocmd("BufWritePost", {
--   pattern = "*.tex",
--   callback = sync_zathura,
-- })
