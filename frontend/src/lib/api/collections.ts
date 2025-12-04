import { apiClient } from "./client";
import type {
  Collection,
  CollectionDetail,
  CollectionListResponse,
  CollectionCreateRequest,
  CollectionUpdateRequest,
  CollectionAddVideosRequest,
} from "../types";

/**
 * Get all collections for the current user
 */
export async function getCollections(): Promise<CollectionListResponse> {
  const response = await apiClient.get("/collections");
  return response.data;
}

/**
 * Get a single collection by ID with all videos
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
 * Add videos to a collection
 */
export async function addVideosToCollection(
  collectionId: string,
  data: CollectionAddVideosRequest
): Promise<CollectionDetail> {
  const response = await apiClient.post(
    `/collections/${collectionId}/videos`,
    data
  );
  return response.data;
}

/**
 * Remove a video from a collection
 */
export async function removeVideoFromCollection(
  collectionId: string,
  videoId: string
): Promise<void> {
  await apiClient.delete(`/collections/${collectionId}/videos/${videoId}`);
}
