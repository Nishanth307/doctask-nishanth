const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function apiClient <T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`,
        {
            headers: {
                "Content-Type": "application/json",
                ...options.headers
            },
            ...options,
        });

        if (!response.ok) {
            let message = `Request failed with status ${response.status}`;

            try {
                const body = await response.json();

                if (typeof body.detail === "string"){
                    message = body.detail;
                }
            } catch {
                // keep the default error message
                
            }

            throw new Error(message);
        }
        return response.json() as Promise<T>;
}