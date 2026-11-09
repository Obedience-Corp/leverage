mod test '.justfiles/test.just'
mod check '.justfiles/check.just'
mod reports '.justfiles/reports.just'

# Run the isolated package gate.
default:
    just test all
