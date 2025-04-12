return {
  "echasnovski/mini.surround",
  event = { "BufRead", "BufNewFile" },
  opts = {
    mappings = {
      add = "sa",
      delete = "sd",
      find = "sf",
      find_left = "gsF",
      -- highlight = "gsh",
      replace = "sr",
      update_n_lines = "sn",
    },
  },
}
