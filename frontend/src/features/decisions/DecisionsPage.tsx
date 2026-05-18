import AskPage from "~/features/ask/AskPage"

/**
 * DecisionsPage is now an alias for Ask Merism.
 *
 * We keep the /decisions route for backward compatibility, but the
 * surface itself is now the Ask Merism experience.
 */
export default function DecisionsPage(): JSX.Element {
    return <AskPage />
}
