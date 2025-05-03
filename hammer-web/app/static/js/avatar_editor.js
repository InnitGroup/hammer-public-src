import { initContainer } from "hammer_3d_renderer";

document.addEventListener('DOMContentLoaded', async function () {
    const itemsOwnedStatusMessage = document.getElementById('items-owned-status-message');
    const itemsEquippedStatusMessage = document.getElementById('items-equipped-status-message');
    const itemsOwnedContainer = document.getElementById('items-owned-container');
    const itemCardTemplate = document.getElementsByClassName('item-card-template')[0];
    const loadingContainer = await HammerLib.get_loading_container();
    const equippedItemsContainer = document.getElementById('items-equipped-container');
    const avatarCategorySelector = document.getElementById('avatar-category-selector');
    const inventoryTypeSelector = document.getElementById('item-type-selector');
    loadingContainer.style.display = 'block';

    const itemsNextPageButton = document.getElementById('items-pagination-next');
    const itemsPreviousPageButton = document.getElementById('items-pagination-prev');
    const itemsPageNumber = document.getElementById('items-pagination-current');
    itemCardTemplate.classList.remove('item-card-template');

    const avatarAccessoriesContainer = document.getElementById('avatar-accessories-container');
    const avatarBodyScalingContainer = document.getElementById('avatar-body-scaling-container');
    const avatarBodyScalingHeightScaler = document.getElementById('body-height-scaler');
    const avatarBodyScalingWidthScaler = document.getElementById('body-width-scaler');
    const avatarBodyScalingHeadScaler = document.getElementById('body-head-scaler');
    const avatarBodyScalingProportionScaler = document.getElementById('body-proportions-scaler');

    const avatarBodyColourPartText = document.getElementById('body-colour-part-name-text');
    const avatarBodyColourContainer = document.getElementById('avatar-body-colours');
    const avatarHeadBody = document.getElementById('head-part');
    const avatarTorsoBody = document.getElementById('torso-part');
    const avatarLeftArmBody = document.getElementById('left-arm-part');
    const avatarRightArmBody = document.getElementById('right-arm-part');
    const avatarLeftLegBody = document.getElementById('left-leg-part');
    const avatarRightLegBody = document.getElementById('right-leg-part');

    const bodyColoursPopupContainer = document.getElementById('body-colours-popup-container');
    const bodyColourTemplate = document.getElementsByClassName('body-colour-template')[0];
    const bodyColoursSelectorContainer = document.getElementById('body-colours-selector-container');

    const BaseURL = await HammerLib.get_endpoint('base_url');
    const assetThumbnailBaseURL = await HammerLib.get_endpoint('thumbnail_asset');
    const inventoryEndpoint = (await HammerLib.get_endpoint('user_inventory_sort_assettype')).replace('<user_id>', HammerLib.authenticated_user_info.userid);

    const avatarRigTypeButton = document.getElementById('avatar-rig-type-btn');

    const avatarPreviewContainer = document.getElementById('avatar-preview-container');
    const avatarPreviewTypeButton = document.getElementById('avatar-preview-selector-btn');
    const avatarPreview2DHolder = document.getElementById('avatar-preview-2d-holder');
    const avatarPreview2DLoadingContainer = document.getElementById('avatar-preview-2d-loading-container');
    const avatarPreview3DHolder = document.getElementById('avatar-preview-3d-holder');
    const avatarPreview3DLoadingContainer = document.getElementById('avatar-preview-3d-loading-container');
    var current_3d_container = null;
    var current_2d_container = null;

    var avatarRules = null;
    var avatarHeadColorId = 0;
    var avatarTorsoColorId = 0;
    var avatarLeftArmColorId = 0;
    var avatarRightArmColorId = 0;
    var avatarLeftLegColorId = 0;
    var avatarRightLegColorId = 0;

    var avatarHeightScale = 1.0;
    var avatarWidthScale = 1.0;
    var avatarHeadScale = 1.0;
    var avatarProportionScale = 1.0;
    var avatarBodyTypeScale = 1.0;

    var avatar_rig_type = 'R6';

    var asset_type_counter = {}
    var asset_info_lookup = {}
    var assets_currently_equipped = []
    var emotes_equipped = {}
    var avatar_hash = null;
    var user_thumbnail_status = null;

    var selected_body_part = 0;

    const update_assets_cooldown_ms = 600;
    var last_update_wearing_assets_request = 0;
    var update_wearing_assets_waiting_req = null;

    const update_body_colours_cooldown_ms = 600;
    var last_update_body_colours_request = 0;
    var update_body_colours_waiting_req = null;

    const update_body_scales_cooldown_ms = 600;
    var last_update_body_scales_request = 0;
    var update_body_scales_waiting_req = null;

    const update_rig_type_cooldown_ms = 600;
    var last_update_rig_type_request = 0;
    var update_rig_type_waiting_req = null;

    async function update_user_preffered_view(is3D) {
        localStorage.setItem('is_3d_preffered_view_type', is3D);
    }

    async function getBrickColorInfo( brickcolor_id ) {
        for ( let brickcolor of avatarRules.bodyColorsPalette ) {
            if ( brickcolor.brickColorId == brickcolor_id ) {
                return brickcolor;
            }
        }
        return null;
    }

    async function updateBodyPartColoursUI() {
        var head_color_info = await getBrickColorInfo(avatarHeadColorId);
        var torso_color_info = await getBrickColorInfo(avatarTorsoColorId);
        var left_arm_color_info = await getBrickColorInfo(avatarLeftArmColorId);
        var right_arm_color_info = await getBrickColorInfo(avatarRightArmColorId);
        var left_leg_color_info = await getBrickColorInfo(avatarLeftLegColorId);
        var right_leg_color_info = await getBrickColorInfo(avatarRightLegColorId);

        avatarHeadBody.style.backgroundColor = head_color_info.hexColor;
        avatarTorsoBody.style.backgroundColor = torso_color_info.hexColor;
        avatarLeftArmBody.style.backgroundColor = left_arm_color_info.hexColor;
        avatarRightArmBody.style.backgroundColor = right_arm_color_info.hexColor;
        avatarLeftLegBody.style.backgroundColor = left_leg_color_info.hexColor;
        avatarRightLegBody.style.backgroundColor = right_leg_color_info.hexColor;
    }

    async function fetchThumbnailStatus() {
        try {
            const fetch_response = await fetch( (await HammerLib.get_endpoint('thumbnail_user_status')).replace( '<user_id>', HammerLib.authenticated_user_info.userid ) );
            if ( fetch_response.status !== 200 ) {
                throw new Error(`avatar_editor.fetchThumbnailStatus > Failed to fetch thumbnail status, unexpected status code: ${fetch_response.status} ${fetch_response.statusText}`);
            }
            const fetch_json = await fetch_response.json();
            user_thumbnail_status = fetch_json;
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while fetching your avatar, please try again.', true);
            return null;
        }
    }

    async function initalise2DContainer() {
        if ( current_2d_container != null ) {
            current_2d_container.remove();
        }
        current_2d_container = document.createElement('img');
        current_2d_container.src = `${await HammerLib.get_endpoint('user_2d_avatar_thumb')}?userId=${HammerLib.authenticated_user_info.userid}&x=352&y=352&format=webp&cacheHash=${avatar_hash}`;
        current_2d_container.style.width = '100%';
        current_2d_container.style.height = '100%';
        avatarPreview2DHolder.appendChild(current_2d_container);
        await new Promise( resolve => current_2d_container.onload = resolve );
    }

    async function initalise3DContainer() {
        if ( current_3d_container != null ) {
            current_3d_container.remove();
        }
        current_3d_container = document.createElement('div');
        current_3d_container.setAttribute('data-render-type', 'user_avatar');
        current_3d_container.setAttribute('data-user-id', HammerLib.authenticated_user_info.userid);
        current_3d_container.style.width = '100%';
        current_3d_container.style.aspectRatio = '1/1';
        avatarPreview3DHolder.appendChild(current_3d_container);
        await initContainer(current_3d_container, avatar_hash, true);
    }

    async function refreshThumbnails() {
        if ( current_3d_container != null ) {
            current_3d_container.remove();
        }
        if ( current_2d_container != null ) {
            current_2d_container.remove();
        }
        const avatar_hash_state = avatar_hash;
        avatarPreview3DLoadingContainer.style.display = 'flex';
        avatarPreview2DLoadingContainer.style.display = 'flex';
        var is3DThumbnailInitialized = false;
        var is2DThumbnailInitialized = false;
        while ( true ) {
            await fetchThumbnailStatus();
            if ( user_thumbnail_status.body_3d == "Completed" && !is3DThumbnailInitialized ) {
                initalise3DContainer().then(() => {
                    avatarPreview3DLoadingContainer.style.display = 'none';
                });
                is3DThumbnailInitialized = true;
            }
            if ( user_thumbnail_status.full_body == "Completed" && !is2DThumbnailInitialized ) {
                initalise2DContainer().then(() => {
                    avatarPreview2DLoadingContainer.style.display = 'none';
                });
                is2DThumbnailInitialized = true;
            }
            if ( ( is3DThumbnailInitialized && is2DThumbnailInitialized ) || avatar_hash_state != avatar_hash ) {
                break;
            }
            await new Promise( resolve => setTimeout(resolve, 800) );
        }
    }

    async function updateRigType() {
        if ( last_update_rig_type_request + update_rig_type_cooldown_ms > Date.now() ) {
            var waiting_guid = Math.random();
            update_rig_type_waiting_req = waiting_guid;
            await new Promise( resolve => setTimeout(resolve, last_update_rig_type_request + update_rig_type_cooldown_ms - Date.now()) );
        
            if ( update_rig_type_waiting_req != waiting_guid ) {
                return;
            }
        }
        last_update_rig_type_request = Date.now();
        try {
            const update_response = await fetch(
                await HammerLib.get_endpoint('avatar_set_rig_type'),
                {
                    credentials : 'include',
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await HammerLib.get_csrf_token()
                    },
                    body: JSON.stringify({
                        "playerAvatarType": avatar_rig_type
                    })
                }
            )
            if ( update_response.status !== 200 ) {
                throw new Error(`avatar_editor.updateRigType > Failed to update rig type, unexpected status code: ${update_response.status} ${update_response.statusText}`);
            }
            const update_json = await update_response.json();
            avatar_hash = update_json.avatar_hash;

            refreshThumbnails();
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while updating your avatar, please try again.', true);
            return null;
        }
    }

    async function updateBodyScales() {
        if ( last_update_body_scales_request + update_body_scales_cooldown_ms > Date.now() ) {
            var waiting_guid = Math.random();
            update_body_scales_waiting_req = waiting_guid;
            await new Promise( resolve => setTimeout(resolve, last_update_body_scales_request + update_body_scales_cooldown_ms - Date.now()) );
        
            if ( update_body_scales_waiting_req != waiting_guid ) {
                return;
            }
        }
        last_update_body_scales_request = Date.now();
        try {
            const update_response = await fetch(
                await HammerLib.get_endpoint('avatar_set_body_scales'),
                {
                    credentials : 'include',
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await HammerLib.get_csrf_token()
                    },
                    body: JSON.stringify({
                        "height": avatarHeightScale,
                        "width": avatarWidthScale,
                        "head": avatarHeadScale,
                        "proportion": avatarProportionScale,
                        "bodyType": avatarBodyTypeScale
                    })
                }
            );
            if ( update_response.status !== 200 ) {
                throw new Error(`avatar_editor.updateBodyScales > Failed to update body scales, unexpected status code: ${update_response.status} ${update_response.statusText}`);
            }
            const update_json = await update_response.json();
            avatar_hash = update_json.avatar_hash;

            refreshThumbnails();
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while updating your avatar, please try again.', true);
            return null;
        }
    }

    async function updateBodyColours() {
        if ( last_update_body_colours_request + update_body_colours_cooldown_ms > Date.now() ) {
            var waiting_guid = Math.random();
            update_body_colours_waiting_req = waiting_guid;
            await new Promise( resolve => setTimeout(resolve, last_update_body_colours_request + update_body_colours_cooldown_ms - Date.now()) );
        
            if ( update_body_colours_waiting_req != waiting_guid ) {
                return;
            }
        }
        last_update_body_colours_request = Date.now();
        try {
            const update_response = await fetch(
                await HammerLib.get_endpoint('avatar_set_body_colors'),
                {
                    credentials : 'include',
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await HammerLib.get_csrf_token()
                    },
                    body: JSON.stringify({
                        "headColorId": avatarHeadColorId,
                        "torsoColorId": avatarTorsoColorId,
                        "leftArmColorId": avatarLeftArmColorId,
                        "rightArmColorId": avatarRightArmColorId,
                        "leftLegColorId": avatarLeftLegColorId,
                        "rightLegColorId": avatarRightLegColorId
                    })
                }
            )
            if ( update_response.status !== 200 ) {
                throw new Error(`avatar_editor.updateBodyColours > Failed to update body colours, unexpected status code: ${update_response.status} ${update_response.statusText}`);
            }
            const update_json = await update_response.json();
            avatar_hash = update_json.avatar_hash;
            refreshThumbnails();
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while updating your avatar, please try again.', true);
            return null;
        }
    }

    async function updateWearingAssets() {
        if ( last_update_wearing_assets_request + update_assets_cooldown_ms > Date.now() ) {
            /*
                Acts as a client side rate limiter and always make sure the last request is the one that gets sent
            */
            var waiting_guid = Math.random();
            update_wearing_assets_waiting_req = waiting_guid;
            await new Promise( resolve => setTimeout(resolve, last_update_wearing_assets_request + update_assets_cooldown_ms - Date.now()) );
        
            if ( update_wearing_assets_waiting_req != waiting_guid ) {
                return;
            }
        }
        last_update_wearing_assets_request = Date.now();
        try {
            const update_response = await fetch(
                await HammerLib.get_endpoint('avatar_set_wearing_assets'),
                {
                    credentials : 'include',
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await HammerLib.get_csrf_token()
                    },
                    body: JSON.stringify({
                        "assetIds": assets_currently_equipped
                    })
                }
            )
            if ( update_response.status !== 200 ) {
                throw new Error(`avatar_editor.updateWearingAssets > Failed to update wearing assets, unexpected status code: ${update_response.status} ${update_response.statusText}`);
            }
            const update_json = await update_response.json();
            avatar_hash = update_json.avatar_hash;
            refreshThumbnails();
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while updating your avatar, please try again.', true);
            return null;
        }
    }

    async function getAssetTypeCount( asset_type ) {
        if ( asset_type_counter[asset_type] == null ) {
            asset_type_counter[asset_type] = 0;
        }
        return asset_type_counter[asset_type];
    }

    async function recountAssetTypes() {
        asset_type_counter = {};
        for ( let asset_id of assets_currently_equipped ) {
            let asset_info = asset_info_lookup[asset_id];
            let asset_type = asset_info['type'];
            if ( asset_type_counter[asset_type] == null ) {
                asset_type_counter[asset_type] = 0;
            }
            asset_type_counter[asset_type]++;
        }
    }

    async function getAssetTypeLimit( asset_type ) {
        for ( let rule of avatarRules.wearableAssetTypes ) {
            if ( rule.id == asset_type ) {
                return rule.maxNumber;
            }
        }
        return null;
    }

    async function getLastAssetByAssetType( asset_type ) {
        for ( let asset_id of assets_currently_equipped ) {
            let asset_info = asset_info_lookup[asset_id];
            if ( asset_info['type'] == asset_type ) {
                return asset_id;
            }
        }
        return null;
    }

    async function unequipAsset( asset_id ) {
        if ( !await isAssetEquipped(asset_id) ) {
            return;
        }

        assets_currently_equipped = assets_currently_equipped.filter( equipped_asset_id => equipped_asset_id != asset_id );
        await recountAssetTypes();
        await updateEquippedAssets();
        updateWearingAssets();
    }

    async function equipAsset( asset_id ) {
        if ( await isAssetEquipped(asset_id) ) {
            return;
        }
        const asset_info = asset_info_lookup[asset_id];
        const asset_type = asset_info['type'];
        const asset_type_limit = await getAssetTypeLimit(asset_type);
        const asset_type_count = await getAssetTypeCount(asset_type);
        if ( asset_type_count >= asset_type_limit ) {
            var last_asset_id = await getLastAssetByAssetType(asset_type);
            await unequipAsset(last_asset_id);
        }
        if ( asset_type_limit == 0 ) {
            return;
        }

        if ( assets_currently_equipped.length >= avatarRules.maxWearables ) {
            var last_asset_id = assets_currently_equipped[0];
            await unequipAsset(last_asset_id);
        }

        assets_currently_equipped.push( Number(asset_id) );
        await recountAssetTypes();
        await updateEquippedAssets();
        const newItemCard = await createItemCard(asset_id, asset_info['name']);
        newItemCard.setAttribute('is-equipped-card', true);
        newItemCard.addEventListener('click', async function () {
            await unequipAsset(asset_id);
        });
        equippedItemsContainer.appendChild(newItemCard);
        updateWearingAssets();
    }

    async function updateEquippedAssets() {
        const all_asset_cards = equippedItemsContainer.getElementsByClassName('item-card');
        for ( let asset_card of all_asset_cards ) {
            const asset_id = Number(asset_card.getAttribute('asset-id'));
            const is_equipped = await isAssetEquipped(asset_id);
            const is_equipped_card = asset_card.getAttribute('is-equipped-card') == 'true';
            if ( is_equipped_card && !is_equipped ) {
                asset_card.remove();
                continue;
            }
            await updateItemCardStatus( asset_card, is_equipped );
        }

        if ( assets_currently_equipped.length == 0 ) {
            itemsEquippedStatusMessage.style.display = 'block';
            itemsEquippedStatusMessage.textContent = 'No items equipped';
        } else {
            itemsEquippedStatusMessage.style.display = 'none';
            itemsEquippedStatusMessage.textContent = '';
        }
    }

    async function isAssetEquipped( asset_id ) {
        for ( let equipped_asset_id of assets_currently_equipped ) {
            if ( equipped_asset_id == asset_id ) {
                return true;
            }
        }
        return false;
    }

    async function updateAvatarRules() {
        try {
            const fetch_response = await fetch( await HammerLib.get_endpoint('avatar_rules') );
            if ( fetch_response.status !== 200 ) {
                throw new Error(`avatar_editor.fetchAvatarRules > Failed to fetch avatar rules, unexpected status code: ${fetch_response.status} ${fetch_response.statusText}`);
            }
            const fetch_json = await fetch_response.json();
            avatarRules = fetch_json;
            await updateBodyColourChoices();
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while fetching avatar rules, please try again.', true);
            return null;
        }
    }

    async function updateBodyColourChoices() {
        for ( let oldChildren of bodyColoursSelectorContainer.children ) {
            oldChildren.remove();
        }
        for ( let brickColor of avatarRules.bodyColorsPalette ) {
            var newBodyColour = bodyColourTemplate.cloneNode(true);
            newBodyColour.style.backgroundColor = brickColor.hexColor;
            newBodyColour.style.display = 'block';
            newBodyColour.addEventListener('click', async function () {
                switch ( selected_body_part ) {
                    case 0:
                        avatarHeadColorId = brickColor.brickColorId;
                        break;
                    case 1:
                        avatarTorsoColorId = brickColor.brickColorId;
                        break;
                    case 2:
                        avatarLeftArmColorId = brickColor.brickColorId;
                        break;
                    case 3:
                        avatarRightArmColorId = brickColor.brickColorId;
                        break;
                    case 4:
                        avatarLeftLegColorId = brickColor.brickColorId;
                        break;
                    case 5:
                        avatarRightLegColorId = brickColor.brickColorId;
                        break;
                }
                await updateBodyPartColoursUI();
                updateBodyColours();
                bodyColoursPopupContainer.style.display = 'none';
            });
            bodyColoursSelectorContainer.appendChild(newBodyColour);
        }
    }

    async function updateUserAvatar() {
        try {
            const fetch_response = await fetch(
                await HammerLib.get_endpoint('avatar_self'),
                {
                    credentials : 'include'
                }
            );
            if ( fetch_response.status !== 200 ) {
                throw new Error(`avatar_editor.fetchUserAvatar > Failed to fetch user avatar, unexpected status code: ${fetch_response.status} ${fetch_response.statusText}`);
            }
            const fetch_json = await fetch_response.json();
            avatarHeadColorId = fetch_json.bodyColors.headColorId;
            avatarTorsoColorId = fetch_json.bodyColors.torsoColorId;
            avatarLeftArmColorId = fetch_json.bodyColors.leftArmColorId;
            avatarRightArmColorId = fetch_json.bodyColors.rightArmColorId;
            avatarLeftLegColorId = fetch_json.bodyColors.leftLegColorId;
            avatarRightLegColorId = fetch_json.bodyColors.rightLegColorId;

            avatarHeightScale = fetch_json.scales.height;
            avatarWidthScale = fetch_json.scales.width;
            avatarHeadScale = fetch_json.scales.head;
            avatarProportionScale = fetch_json.scales.proportion;
            avatarBodyTypeScale = fetch_json.scales.bodyType;

            for ( let asset of fetch_json.assets ) {
                asset_info_lookup[asset.id] = {
                    'id': asset.id,
                    'name': asset.name,
                    'type': asset.assetType.id,
                }
                assets_currently_equipped.push(asset.id);
            }
            for ( let emote of fetch_json.emotes ) {
                emotes_equipped[emote.position] = {
                    'id': emote.id,
                    'name': emote.name,
                }
            }
            avatar_rig_type = fetch_json.playerAvatarType;
            avatar_hash = fetch_json.avatar_hash;
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while fetching your avatar, please try again.', true);
            return null;
        }
    }

    async function createItemCard( asset_id, asset_name ) {
        const newItemCard = itemCardTemplate.cloneNode(true);
        const itemCardThumbnail = newItemCard.getElementsByClassName('item-card-thumbnail')[0];
        const itemCardName = newItemCard.getElementsByClassName('item-card-name')[0];

        itemCardThumbnail.src = `${assetThumbnailBaseURL}?assetId=${asset_id}&format=webp&x=100&y=100`;
        itemCardName.textContent = asset_name;
        itemCardName.href = `${BaseURL}/catalog/${asset_id}/--`;
        newItemCard.style.display = 'block';
        newItemCard.classList.add('item-card');
        newItemCard.setAttribute('asset-id', asset_id);

        if ( await isAssetEquipped(asset_id) ) {
            itemCardThumbnail.classList.remove('border-gray-400');
            itemCardThumbnail.classList.add('border-indigo-700');
        }

        return newItemCard;
    }

    async function updateItemCardStatus( item_card, is_equipped ) {
        const itemCardThumbnail = item_card.getElementsByClassName('item-card-thumbnail')[0];
        if ( is_equipped ) {
            itemCardThumbnail.classList.remove('border-gray-400');
            itemCardThumbnail.classList.add('border-indigo-700');
        } else {
            itemCardThumbnail.classList.remove('border-indigo-700');
            itemCardThumbnail.classList.add('border-gray-400');
        }
    }

    async function parseItemsOwned( itemsOwned ) {
        for (let item of itemsOwned) {
            var newItemCard = await createItemCard(item.assetId, item.assetName);
            itemsOwnedContainer.appendChild(newItemCard);

            newItemCard.addEventListener('click', async function () {
                var asset_id = newItemCard.getAttribute('asset-id');
                var is_equipped = await isAssetEquipped(asset_id);
                if ( is_equipped ) {
                    await unequipAsset(asset_id);
                } else {
                    await equipAsset(asset_id);
                }
                await updateItemCardStatus( newItemCard, await isAssetEquipped(asset_id) );
            })
        }
    }

    var nextPageCursor = null;
    var previousPageCursor = null;
    var pageNumber = 1;

    async function updatePagination() {
        itemsPageNumber.textContent = `Page ${pageNumber}`;
        if ( nextPageCursor == null ) {
            itemsNextPageButton.disabled = true;
        } else {
            itemsNextPageButton.disabled = false;
        }
        if ( previousPageCursor == null ) {
            itemsPreviousPageButton.disabled = true;
        } else {
            itemsPreviousPageButton.disabled = false;
        }
    }

    async function fetchItemsOwned( assetType, cursor = null ) {
        try {
            const fetch_response = await fetch(
                `${inventoryEndpoint.replace('<asset_type>', assetType)}?limit=10&sortOrder=Desc${cursor ? `&cursor=${cursor}` : ''}`,
                {
                    credentials : 'include'
                }
            )
            if ( fetch_response.status !== 200 ) {
                if ( fetch_response.status === 429 ) {
                    console.log('avatar_editor.fetchItemsOwned > Rate limited while fetching inventory, retrying in 1.5 seconds');
                    await new Promise( resolve => setTimeout(resolve, 1500) );
                    return await fetchItemsOwned(assetType, cursor);
                }
                throw new Error(`avatar_editor.fetchItemsOwned > Failed to fetch inventory, unexpected status code: ${fetch_response.status} ${fetch_response.statusText}`);
            }
            const fetch_json = await fetch_response.json();

            if ( cursor == null ) {
                pageNumber = 1;
            } else if ( cursor == nextPageCursor ) {
                pageNumber++;
            } else if ( cursor == previousPageCursor ) {
                pageNumber--;
            }
            nextPageCursor = fetch_json.nextPageCursor;
            previousPageCursor = fetch_json.previousPageCursor;

            for ( let asset of fetch_json.data ) {
                asset_info_lookup[asset.assetId] = {
                    'id': asset.assetId,
                    'name': asset.assetName,
                    'type': assetType,
                }
            }
            
            return fetch_json.data;
        } catch (error) {
            console.error(error);
            await HammerLib.show_error_dialog('Internal Error', 'An error occurred while fetching your inventory.', false);
            return [];
        }
    }

    async function loadItemTypePage( assetType, cursor = null ) {
        itemsOwnedContainer.innerHTML = '';
        itemsOwnedStatusMessage.style.display = 'block';
        itemsOwnedStatusMessage.textContent = 'Fetching items';
        itemsNextPageButton.disabled = true;
        itemsPreviousPageButton.disabled = true;
        inventoryTypeSelector.disabled = true;

        var itemsOwnedPromise = fetchItemsOwned(assetType, cursor);
        // Feels weird when it loads instantly without a delay
        // The selector doesent even get to finish its closing animation before the items are loaded
        // This shouldn't affect user experience too much since you cant even see the items until the selector is closed
        // At the same time this is an effective method of client side rate limiting
        // - something.else 13/08/2024
        await new Promise( resolve => setTimeout(resolve, 160) ); 
        var itemsOwned = await itemsOwnedPromise;
        if ( itemsOwned.length == 0 ) {
            itemsOwnedStatusMessage.style.display = 'block';
            itemsOwnedStatusMessage.textContent = 'No items found';
            inventoryTypeSelector.disabled = false;
            updatePagination();
            return;
        }
        itemsOwnedStatusMessage.textContent = '';
        itemsOwnedStatusMessage.style.display = 'none';
        await parseItemsOwned(itemsOwned);
        updatePagination();
        inventoryTypeSelector.disabled = false;
    }

    async function setupScalingSlider( scale_rules, scale_element, initial_value, scale_callback ) {
        const scale_slider = scale_element.getElementsByClassName('scale-slider')[0];
        const scale_value = scale_element.getElementsByClassName('scaling-value')[0];
        scale_slider.min = scale_rules.min * 100;
        scale_slider.max = scale_rules.max * 100;
        scale_slider.value = initial_value * 100;
        scale_slider.step = scale_rules.increment * 100;
        scale_value.textContent = `${initial_value * 100}%`;
        scale_slider.addEventListener('sl-change', async function () {
            const new_value = scale_slider.value / 100;
            scale_value.textContent = `${new_value * 100}%`;
            scale_callback(new_value);
        });
        scale_slider.addEventListener('input', async function () {
            const new_value = scale_slider.value / 100;
            scale_value.textContent = `${new_value * 100}%`;
        });
    }

    var currentAssetType = 8;
    var user_thumbnail_status_promise = fetchThumbnailStatus();
    var avatar_rules_promise = updateAvatarRules();
    var user_avatar_promise = updateUserAvatar();
    var load_user_inventory_promise = loadItemTypePage(currentAssetType);

    inventoryTypeSelector.addEventListener('sl-change', async function () {
        currentAssetType = inventoryTypeSelector.value;
        await loadItemTypePage(currentAssetType);
    });
    itemsNextPageButton.addEventListener('click', async function () {
        await loadItemTypePage(currentAssetType, nextPageCursor);
    });
    itemsPreviousPageButton.addEventListener('click', async function () {
        await loadItemTypePage(currentAssetType, previousPageCursor);
    });

    avatarHeadBody.addEventListener('click', async function () {
        selected_body_part = 0;
        avatarBodyColourPartText.textContent = 'Head';
        bodyColoursPopupContainer.style.display = 'block';
    });

    avatarTorsoBody.addEventListener('click', async function () {
        selected_body_part = 1;
        avatarBodyColourPartText.textContent = 'Torso';
        await new Promise( resolve => setTimeout(resolve, 10) );
        bodyColoursPopupContainer.style.display = 'block';
    });

    avatarLeftArmBody.addEventListener('click', async function () {
        await new Promise( resolve => setTimeout(resolve, 10) );
        selected_body_part = 2;
        avatarBodyColourPartText.textContent = 'Left Arm';
        bodyColoursPopupContainer.style.display = 'block';
    });

    avatarRightArmBody.addEventListener('click', async function () {
        await new Promise( resolve => setTimeout(resolve, 10) );
        selected_body_part = 3;
        avatarBodyColourPartText.textContent = 'Right Arm';
        bodyColoursPopupContainer.style.display = 'block';
    });

    avatarLeftLegBody.addEventListener('click', async function () {
        selected_body_part = 4;
        avatarBodyColourPartText.textContent = 'Left Leg';
        bodyColoursPopupContainer.style.display = 'block';
    });

    avatarRightLegBody.addEventListener('click', async function () {
        selected_body_part = 5;
        avatarBodyColourPartText.textContent = 'Right Leg';
        bodyColoursPopupContainer.style.display = 'block';
    });

    await Promise.all([user_thumbnail_status_promise, avatar_rules_promise, user_avatar_promise, load_user_inventory_promise]);
    for ( let asset_id of assets_currently_equipped ) {
        const asset_info = asset_info_lookup[asset_id];
        const newItemCard = await createItemCard(asset_id, asset_info['name']);
        newItemCard.setAttribute('is-equipped-card', true);
        newItemCard.addEventListener('click', async function () {
            await unequipAsset(asset_id);
        });
        equippedItemsContainer.appendChild(newItemCard);
    }

    await setupScalingSlider( avatarRules.scales.height, avatarBodyScalingHeightScaler, avatarHeightScale, async function ( new_value ) { avatarHeightScale = new_value; await updateBodyScales(); } );
    await setupScalingSlider( avatarRules.scales.width, avatarBodyScalingWidthScaler, avatarWidthScale, async function ( new_value ) { avatarWidthScale = new_value; await updateBodyScales();} );
    await setupScalingSlider( avatarRules.scales.head, avatarBodyScalingHeadScaler, avatarHeadScale, async function ( new_value ) { avatarHeadScale = new_value; await updateBodyScales();} );
    await setupScalingSlider( avatarRules.scales.proportion, avatarBodyScalingProportionScaler, avatarProportionScale, async function ( new_value ) { avatarProportionScale = new_value; await updateBodyScales();} );
    await updateEquippedAssets();
    await updateBodyPartColoursUI();
    refreshThumbnails();
    avatarRigTypeButton.innerText = avatar_rig_type == 'R6' ? 'R15' : 'R6';
    loadingContainer.style.display = 'none';

    avatarCategorySelector.addEventListener('sl-change', async function () {
        var selectedCategory = avatarCategorySelector.value;
        avatarAccessoriesContainer.style.display = 'none';
        avatarBodyColourContainer.style.display = 'none';
        avatarBodyScalingContainer.style.display = 'none';
        switch ( selectedCategory ) {
            case 'accessories':
                avatarAccessoriesContainer.style.display = 'block';
                break;
            case 'scaling':
                avatarBodyScalingContainer.style.display = 'block';
                break;
            case 'body-colours':
                avatarBodyColourContainer.style.display = 'block';
                break;
        }
    });

    var is3DPreview = false;
    async function updatePreview() {
        if ( is3DPreview ) {
            avatarPreview2DHolder.style.display = 'block';
            avatarPreview3DHolder.style.display = 'none';
            avatarPreviewTypeButton.innerText = '3D';
        } else {
            avatarPreview2DHolder.style.display = 'none';
            avatarPreview3DHolder.style.display = 'block';
            avatarPreviewTypeButton.innerText = '2D';
            window.dispatchEvent(new Event('resize')); // Force 3D renderer to resize
        }
        is3DPreview = !is3DPreview;
        await update_user_preffered_view(is3DPreview);
    }

    avatarRigTypeButton.addEventListener('click', async function () {
        if ( avatar_rig_type == 'R6' ) {
            avatar_rig_type = 'R15';
            avatarRigTypeButton.innerText = 'R6';
        } else {
            avatar_rig_type = 'R6';
            avatarRigTypeButton.innerText = 'R15';
        }
        updateRigType();
    });

    avatarPreviewTypeButton.addEventListener('click', async function () {
        updatePreview();
    });

    if ( localStorage.getItem('is_3d_preffered_view_type') === 'true' ) {
        updatePreview();
    }
});