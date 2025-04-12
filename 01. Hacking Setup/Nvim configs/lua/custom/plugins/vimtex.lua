return {
  "lervag/vimtex",
  event = "BufRead",
  config = function()
    vim.g.vimtex_view_method = "zathura"
    -- Disable VimTeX default mappings
    vim.g.vimtex_mappings_enabled = 0
    vim.g.vimtex_compiler_latexmk = {
      build_dir = "",
      callback = 1,
      continuous = 1,
      executable = "latexmk",
      options = {
        "-verbose",
        "-file-line-error",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-pdf",
      },
    }
    vim.g.vimtex_view_general_options = "--synctex-forward @line:@col:@file"

    -- This check when I save the file, it apply forward seach by running the :VimtexView
    -- This is fast, so that after you moved to the new place in the pdf, you will reach before compilation finished.
    -- So you will see the changes in front of you.
    vim.cmd [[
      augroup vimtex_user
        autocmd!
        " autocmd BufWritePost <buffer> VimtexView
        autocmd BufWritePost *.tex VimtexView
      augroup END
    ]]

    -- This is another type to apply forward seach (not preferred)
    -- It checks for the VimtexEventCompileSuccess event,
    -- Which is triggered even in the first compilation with the `<localleader>ll`
    -- So in every new compilation for a file, it will open the file twice,
    -- One with the <localleader>ll itself, and one with the VimtexView
    -- vim.cmd [[
    --   augroup vimtex_user
    --     autocmd!
    --     autocmd User VimtexEventCompileSuccess VimtexView
    --   augroup END
    -- ]]

    -- Set mappings for Vimtex
    local opts = { noremap = true, silent = true }
    vim.api.nvim_set_keymap("n", "<localleader>ll", "<Plug>(vimtex-compile)", opts)
    vim.api.nvim_set_keymap("n", "<localleader>lv", "<Plug>(vimtex-view)", opts)
    vim.api.nvim_set_keymap("n", "<localleader>ls", "<Plug>(vimtex-stop)", opts)
    vim.api.nvim_set_keymap("n", "<localleader>lt", ":VimtexTocToggle<CR>", opts)
  end,
}
