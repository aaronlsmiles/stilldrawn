# A13, secondary (no verdict): ordinal mixed model rating ~ drift + study + (1 | row) + (1 | rater).
# A cumulative link mixed model (ordinal::clmm), logit link, Laplace approximation. R and the four packages
# the fit loads (ordinal, ucminf, numDeriv, Matrix) must be the versions analysis/a13-r-lock.txt pins: the run
# refuses any other, and records the versions it loaded. "Converged" means clmm returned and its optimizer's
# convergence code is 0. Otherwise (clmm raised, or the optimizer stopped at a limit or a false or singular
# convergence and returned anyway) the output records "converged": false, the code, the optimizer's message
# or the error, and no coefficient. Both outcomes record the largest absolute gradient, every R warning and
# the rater slots fitted ("raters"), which the report compares with the included raters (ruled 9 Nov 2026).
# Called by analysis/a13_adherence.py --mixed:
#   Rscript --vanilla analysis/a13_mixed.R <input.csv> <output.json> <lock file> <R library folder> [control]
# The fifth argument is for tests only ("iter.max=2"): optimizer settings passed to clmm.control, recorded as
# "test_control" (null in every real run; the report refuses a file that carries one).
# The input has one line per included rating: rating (1-5), drift (released line_chamfer_mean_px),
# study (burst or push: the two questions differ), row (a panel and a motion class) and rater (an opaque slot).
args <- commandArgs(trailingOnly = TRUE)
if (!(length(args) %in% c(4, 5))) stop("usage: a13_mixed.R input.csv output.json lock.txt library [test-only control]")
.libPaths(c(args[4], .libPaths()))
lock <- readLines(args[3])
suppressPackageStartupMessages(library(ordinal))
pinned <- function(name, prefix, have) {
  want <- substring(lock[startsWith(lock, prefix)], nchar(prefix) + 1)
  if (length(want) != 1) stop(sprintf("%s: the lock file names no single version", name))
  if (have != want) stop(sprintf("%s %s is pinned by the lock file; found %s", name, want, have))
  have
}
pinned("R", "R version ", sub("^R version ", "", R.version.string))
pkgs <- c("ordinal", "ucminf", "numDeriv", "Matrix")
loaded <- vapply(pkgs, function(p) {
  if (!(p %in% loadedNamespaces())) stop(sprintf("%s: not loaded with ordinal", p))
  pinned(p, paste0(p, " "), as.character(package_version(getNamespaceVersion(p))))
}, "")
d <- read.csv(args[1], stringsAsFactors = FALSE)
d$rating <- factor(d$rating, levels = 1:5, ordered = TRUE)
d$study <- factor(d$study, levels = c("burst", "push"))
d$row <- factor(d$row)
d$rater <- factor(d$rater)
test_control <- if (length(args) == 5 && nzchar(args[5])) args[5] else NA
opt <- list()
if (!is.na(test_control)) {
  for (kv in strsplit(test_control, ",", fixed = TRUE)[[1]]) {
    p <- strsplit(kv, "=", fixed = TRUE)[[1]]
    opt[[p[1]]] <- as.numeric(p[2])
  }
}
ctl <- do.call(clmm.control, opt)
warns <- character()
collect <- function(expr) withCallingHandlers(expr, warning = function(w) {
  warns <<- c(warns, conditionMessage(w))
  invokeRestart("muffleWarning")
})
m <- tryCatch(collect(clmm(rating ~ drift + study + (1 | row) + (1 | rater), data = d, link = "logit", Hess = TRUE,
                           nAGQ = 1, control = ctl)), error = function(e) e)
num <- function(x) if (length(x) != 1 || is.na(x) || !is.finite(x)) "null" else formatC(x, digits = 15, format = "g")
jstr <- function(x) {
  x <- gsub("[[:cntrl:]]", " ", x)
  x <- gsub("\\", "\\\\", x, fixed = TRUE)
  paste0('"', gsub('"', '\\"', x, fixed = TRUE), '"')
}
jarr <- function(x) paste0("[", paste(vapply(x, jstr, ""), collapse = ", "), "]")
thrown <- inherits(m, "error")
code <- if (thrown || is.null(m$optRes$convergence)) NA else m$optRes$convergence
grad <- if (thrown) NA else max(abs(m$gradient))
converged <- !thrown && !is.na(code) && code == 0
head <- paste0("{\n",
  ' "model": "cumulative link mixed model (ordinal::clmm), logit link, Laplace approximation",\n',
  ' "formula": "rating ~ drift + study + (1 | row) + (1 | rater)",\n',
  ' "r": ', jstr(R.version.string), ',\n',
  ' "packages": {', paste(sprintf("%s: %s", vapply(pkgs, jstr, ""), vapply(loaded, jstr, "")), collapse = ", "), '},\n',
  ' "optimizer": ', jstr(ctl$method), ',\n',
  ' "test_control": ', if (is.na(test_control)) "null" else jstr(test_control), ',\n',
  ' "n_ratings": ', nrow(d), ',\n "n_rows": ', nlevels(d$row), ',\n "n_raters": ', nlevels(d$rater), ',\n',
  ' "raters": ', jarr(sort(levels(d$rater))), ',\n')
if (!converged) {
  msg <- if (thrown) conditionMessage(m) else if (is.null(m$optRes$message)) sprintf("convergence code %s", code) else m$optRes$message
  json <- paste0(head,
    ' "converged": false,\n',
    ' "convergence_code": ', num(code), ',\n',
    ' "error": ', jstr(msg), ',\n',
    ' "max_abs_gradient": ', num(grad), ',\n',
    ' "warnings": ', jarr(warns), ',\n',
    ' "note": "secondary, no verdict (A13); the model did not converge, so no estimate is reported"\n',
    "}\n")
  writeLines(json, args[2], sep = "")
  quit(save = "no", status = 0)
}
s <- collect(summary(m))
co <- s$coefficients
vc <- VarCorr(m)
th <- coef(m)[grepl("|", names(coef(m)), fixed = TRUE)]
json <- paste0(head,
  ' "converged": true,\n',
  ' "convergence_code": ', num(code), ',\n',
  ' "max_abs_gradient": ', num(grad), ',\n',
  ' "warnings": ', jarr(warns), ',\n',
  ' "drift": {"estimate": ', num(co["drift", "Estimate"]), ', "se": ', num(co["drift", "Std. Error"]),
  ', "z": ', num(co["drift", "z value"]), ', "p_two_sided": ', num(co["drift", "Pr(>|z|)"]), '},\n',
  ' "study_push": {"estimate": ', num(co["studypush", "Estimate"]), ', "se": ', num(co["studypush", "Std. Error"]), '},\n',
  ' "thresholds": {', paste(sprintf("%s: %s", vapply(names(th), jstr, ""), vapply(th, num, "")), collapse = ", "), '},\n',
  ' "random_sd": {"row": ', num(sqrt(as.numeric(vc$row))), ', "rater": ', num(sqrt(as.numeric(vc$rater))), '},\n',
  ' "log_likelihood": ', num(as.numeric(logLik(m))), ',\n',
  ' "condition_number_hessian": ', num(if (is.null(s$condHess)) NA else s$condHess), ',\n',
  ' "note": "secondary, no verdict (A13); a positive drift estimate means clips that drift more get higher adherence ratings"\n',
  "}\n")
writeLines(json, args[2], sep = "")
