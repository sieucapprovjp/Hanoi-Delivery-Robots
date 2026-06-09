function buildApiUrl(endpoint, params = null) {
    if (!params) return endpoint;

    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
            searchParams.set(key, value);
        }
    });

    const query = searchParams.toString();
    return query ? `${endpoint}?${query}` : endpoint;
}

async function requestJson(endpoint, options = {}) {
    const {
        method = 'GET',
        params = null,
        body = undefined,
        errorMessage = 'API request failed',
    } = options;

    const fetchOptions = { method };

    if (body !== undefined) {
        fetchOptions.headers = { 'Content-Type': 'application/json' };
        fetchOptions.body = JSON.stringify(body);
    }

    const response = await fetch(buildApiUrl(endpoint, params), fetchOptions);
    let data = null;

    try {
        data = await response.json();
    } catch (_) {
        data = null;
    }

    if (!response.ok) {
        const error = new Error(data?.error || `${errorMessage}: ${response.status}`);
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return data;
}

function getJson(endpoint, params = null, errorMessage = 'GET request failed') {
    return requestJson(endpoint, { params, errorMessage });
}

function postJson(endpoint, body = undefined, errorMessage = 'POST request failed') {
    return requestJson(endpoint, { method: 'POST', body, errorMessage });
}

function putJson(endpoint, body = undefined, errorMessage = 'PUT request failed') {
    return requestJson(endpoint, { method: 'PUT', body, errorMessage });
}
