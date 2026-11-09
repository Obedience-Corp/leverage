mod test '.justfiles/test.just'
mod check '.justfiles/check.just'

# Run the isolated package gate.
default:
    just test all
