import { useEffect } from "react";
import { useSoundsStore } from "@opencut/sounds/sounds-store";
import { searchSounds } from "@opencut/clipnera/sounds";

export function useSoundSearch({
	query,
	commercialOnly,
}: {
	query: string;
	commercialOnly: boolean;
}) {
	const {
		searchResults,
		isSearching,
		searchError,
		lastSearchQuery,
		currentPage,
		hasNextPage,
		isLoadingMore,
		totalCount,
		setSearchResults,
		setSearching,
		setSearchError,
		setLastSearchQuery,
		setCurrentPage,
		setHasNextPage,
		setTotalCount,
		setLoadingMore,
		appendSearchResults,
		appendTopSounds,
		resetPagination,
	} = useSoundsStore();

	const loadMore = async () => {
		if (isLoadingMore || !hasNextPage) return;

		try {
			setLoadingMore({ loading: true });
			const nextPage = currentPage + 1;

			const searchParams = new URLSearchParams({
				page: nextPage.toString(),
				type: "effects",
			});

			if (query.trim()) {
				searchParams.set("q", query);
			}

			// Clipnera: its own sound library (clipnera/sounds.ts); every sound is cleared for commercial use.
			const data = await searchSounds({ q: query.trim(), page: nextPage });

			if (query.trim()) {
				appendSearchResults({ results: data.results });
			} else {
				appendTopSounds({ results: data.results });
			}

			setCurrentPage({ page: nextPage });
			setHasNextPage({ hasNext: !!data.next });
			setTotalCount({ count: data.count });
		} catch (err) {
			setSearchError({
				error: err instanceof Error ? err.message : "Load more failed",
			});
		} finally {
			setLoadingMore({ loading: false });
		}
	};

	useEffect(() => {
		if (!query.trim()) {
			setSearchResults({ results: [] });
			setSearchError({ error: null });
			setLastSearchQuery({ query: "" });
			return;
		}

		if (query === lastSearchQuery && searchResults.length > 0) {
			return;
		}

		let ignore = false;

		const timeoutId = setTimeout(async () => {
			try {
				setSearching({ searching: true });
				setSearchError({ error: null });
				resetPagination();

				const data = await searchSounds({ q: query, page: 1 });

				if (!ignore) {
					setSearchResults({ results: data.results });
					setLastSearchQuery({ query: query });
					setHasNextPage({ hasNext: !!data.next });
					setTotalCount({ count: data.count });
					setCurrentPage({ page: 1 });
				}
			} catch (err) {
				if (!ignore) {
					setSearchError({
						error: err instanceof Error ? err.message : "Search failed",
					});
				}
			} finally {
				if (!ignore) {
					setSearching({ searching: false });
				}
			}
		}, 300);

		return () => {
			clearTimeout(timeoutId);
			ignore = true;
		};
	}, [
		query,
		lastSearchQuery,
		searchResults.length,
		setSearchResults,
		setSearching,
		setSearchError,
		setLastSearchQuery,
		setCurrentPage,
		setHasNextPage,
		setTotalCount,
		resetPagination,
	]);

	return {
		results: searchResults,
		isLoading: isSearching,
		error: searchError,
		loadMore,
		hasNextPage,
		isLoadingMore,
		totalCount,
	};
}
