import { apiClient } from "./client";
import type {
  Collection,
  CollectionDetail,
  CollectionListResponse,
  CollectionCreateRequest,
  CollectionUpdateRequest,
  CollectionAddContentRequest,
  CollectionThemesResponse,
  ClusteredThemesResponse,
} from "../types";

/**
 * Get all collections for the current user
 */
export async function getCollections(): Promise<CollectionListResponse> {
  const response = await apiClient.get("/collections");
  return response.data;
}

/**
 * Get a single collection by ID with all content
 */
export async function getCollection(id: string): Promise<CollectionDetail> {
  const response = await apiClient.get(`/collections/${id}`);
  return response.data;
}

/**
 * Create a new collection
 */
export async function createCollection(
  data: CollectionCreateRequest
): Promise<CollectionDetail> {
  const response = await apiClient.post("/collections", data);
  return response.data;
}

/**
 * Update an existing collection
 */
export async function updateCollection(
  id: string,
  data: CollectionUpdateRequest
): Promise<CollectionDetail> {
  const response = await apiClient.patch(`/collections/${id}`, data);
  return response.data;
}

/**
 * Delete a collection
 */
export async function deleteCollection(id: string): Promise<void> {
  await apiClient.delete(`/collections/${id}`);
}

/**
 * Add content to a collection
 */
export async function addContentToCollection(
  collectionId: string,
  data: CollectionAddContentRequest
): Promise<CollectionDetail> {
  const response = await apiClient.post(
    `/collections/${collectionId}/videos`,
    data
  );
  return response.data;
}

/**
 * Remove content from a collection
 */
export async function removeItemFromCollection(
  collectionId: string,
  videoId: string
): Promise<void> {
  await apiClient.delete(`/collections/${collectionId}/videos/${videoId}`);
}

/**
 * Get aggregated themes/topics for a collection
 */
export async function getCollectionThemes(
  collectionId: string,
  refresh: boolean = false
): Promise<CollectionThemesResponse> {
  const response = await apiClient.get(
    `/collections/${collectionId}/themes`,
    { params: { refresh } }
  );
  return response.data;
}

/**
 * Get clustered themes for a collection
 */
export async function getClusteredThemes(
  collectionId: string
): Promise<ClusteredThemesResponse> {
  const response = await apiClient.get(
    `/collections/${collectionId}/themes/clustered`
  );
  return response.data;
}

/**
 * Trigger async regeneration of clustered themes
 */
export async function regenerateCollectionThemes(
  collectionId: string
): Promise<{ message: string; task_id: string; collection_id: string }> {
  const response = await apiClient.post(
    `/collections/${collectionId}/themes/regenerate`
  );
  return response.data;
}
