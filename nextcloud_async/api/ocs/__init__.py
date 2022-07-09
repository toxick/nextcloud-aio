"""Request Wrapper for Nextcloud OCS APIs.

https://docs.nextcloud.com/server/latest/developer_manual/client_apis/OCS/ocs-api-overview.html
"""

import json

from typing import Dict, Any, Optional, List

from nextcloud_async.api import NextCloudBaseAPI
from nextcloud_async.exceptions import NextCloudAsyncException


class NextCloudOCSAPI(NextCloudBaseAPI):
    """Nextcloud OCS API.

    All OCS queries must have an {'OCS-APIRequest': 'true'} header. Additionally, we
    request all data to be returned to us in json format.
    """

    __capabilities = None

    async def ocs_query(
            self,
            method: str,
            url: str = None,
            sub: str = '',
            data: Dict[Any, Any] = {},
            headers: Dict[Any, Any] = {},
            include_headers: Optional[List] = []) -> Dict:
        """Submit OCS-type query to cloud endpoint.

        Args
        ----
            method (str): HTTP Method (eg, `GET`, `POST`, etc...)

            url (str, optional): Use a URL outside of the given endpoint. Defaults to None.

            sub (str, optional): The portion of the URL after the host. Defaults to ''.

            data (Dict, optional): Data for submission.  Data for GET requests is translated by
            urlencode and tacked on to the end of the URL as arguments. Defaults to {}.

            headers (Dict, optional): Headers for submission. Defaults to {}.

            include_headers (List, optional): Return these headers from response.
            Defaults to [].

        Raises
        ------
            NextCloudAsyncException: Server API Errors

        Returns
        -------
            Dict: Response Data

            The OCS Endpoint returns metadata about the response in addition to the data
            what was requested.  The metadata is stripped after checking for request
            success, and only the data portion of the response is returned.

            >>> response = await self.ocs_query(sub='/ocs/v1.php/cloud/capabilities')

            Dict, Dict: Response Data and Included Headers

            If ocs_query() is called with an `include_headers` argument, both response data
            and the requested headers are returned.

            >>> response, headers = await self.ocs_query(..., include_headers=['Some-Header'])

        """
        response_headers = {}
        headers.update({'OCS-APIRequest': 'true'})
        data.update({"format": "json"})

        response = await self.request(
            method, url=url, sub=sub, data=data, headers=headers)

        if response.content:
            response_content = json.loads(response.content.decode('utf-8'))
            ocs_meta = response_content['ocs']['meta']
            if ocs_meta['status'] != 'ok':
                raise NextCloudAsyncException(
                    f'{ocs_meta["statuscode"]}: {ocs_meta["message"]}')
            else:
                response_data = response_content['ocs']['data']
                if include_headers:
                    for header in include_headers:
                        response_headers.setdefault(header, response.headers.get(header, None))
                    return response_data, response_headers
                else:
                    return response_data
        else:
            return None

    async def get_capabilities(self, slice: Optional[str] = '') -> Dict:
        """Get and cache capabilities for this server.

        Args
        ----
            slice (str optional): Only return specific portion of results. Defaults to ''.

        Returns
        -------
            Dict: Capabilities filtered by slice.

        """
        if not self.__capabilities:
            self.__capabilities = await self.ocs_query(
                method='GET',
                sub=r'/ocs/v1.php/cloud/capabilities')
        ret = self.__capabilities

        for item in slice.split('.'):
            ret = ret[item] if item else ret

        return ret

    async def get_file_guest_link(self, file_id: int) -> str:
        """Generate a generic sharable link for a file.

        Link expires in 8 hours.

        Args
        ----
            file_id (int): File ID to generate link for

        Returns
        -------
            str: Link to file

        """
        result = await self.ocs_query(
            method='POST',
            sub=r'/ocs/v2.php/apps/dav/api/v1/direct',
            data={'fileId': file_id})
        return result['url']

    async def get_activity(
            self,
            since: Optional[int] = 0,
            object_id: Optional[str] = None,
            object_type: Optional[str] = None,
            sort: Optional[str] = 'desc',
            limit: Optional[int] = 50):
        """Get Recent activity for the current user.

        Args
        ----
            since (int optional): Only return ativity since activity with given ID. Defaults
            to 0.

            object_id (str optional): object_id filter. Defaults to None.

            object_type (str optional): object_type filter. Defaults to None.

            sort (str optional): Sort order; either `asc` or `desc`. Defaults to 'desc'.

            limit (int optional): How many results per request. Defaults to 50.

        Raises
        ------
            NextCloudAsyncException: When given invalid argument combination

        Returns
        -------
            dict: activity results

        """
        data = {}
        filter = ''
        if object_id and object_type:
            filter = '/filter'
            data.update({
                'object_type': object_type,
                'object_id': object_id})
        elif object_id or object_type:
            raise NextCloudAsyncException(
                'filter_object_type and filter_object are both required.')

        data.update({
            'limit': limit,
            'sort': sort,
            'since': since})

        return await self.ocs_query(
            method='GET',
            sub=f'/ocs/v2.php/apps/activity/api/v2/activity{filter}',
            data=data,
            include_headers=['X-Activity-First-Known', 'X-Activity-Last-Given'])
