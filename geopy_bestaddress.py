import collections.abc
from functools import partial
from urllib.parse import urlencode

from geopy.exc import ConfigurationError, GeocoderQueryError, GeocoderAuthenticationFailure
from geopy.geocoders.base import _DEFAULT_USER_AGENT, DEFAULT_SENTINEL, Geocoder
from geopy.location import Location
from geopy.util import logger

import urllib3
import json

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

__all__ = ("BestAddress", )



def coalesce(dct, keys):
    for k in keys:
        if k in dct:
            return dct[k]
    return None

class BestAddress(Geocoder):
    
    _DEFAULT_BEST_DOMAIN  ="privateservices-int.socialsecurity.be"

    #geocode_path = '/api/belgianAddress/v2/addresses'

    
    authorization_path = "/REST/publicFedServicesGateway/v1/api/oauth2/token"
    
    street_path = "/REST/publicFedServicesGateway/v1/api/best/v1/belgianAddress/v2/streets"

    address_path =  "/REST/publicFedServicesGateway/v1/api/best/v1/belgianAddress/v2/addresses"
    
    city_path =  "/REST/publicFedServicesGateway/v1/api/best/v1/belgianAddress/v2/postalInfos"

    scope             = "BOSA"

    belgov_trace_id="77ce8201c060-342bfe84-1d4c-4730-666"
    
    
    def __init__(
            self,
            *,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            domain=_DEFAULT_BEST_DOMAIN,
            scheme="https",
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
            adapter_factory=None,
            client_id=None,
            client_secret=None,
            token=None,
            verbose=False
            # Make sure to synchronize the changes of this signature in the
            # inheriting classes (e.g. PickPoint).
    ):
        """

        :param int timeout:
            See :attr:`geopy.geocoders.options.default_timeout`.

        :param dict proxies:
            See :attr:`geopy.geocoders.options.default_proxies`.

        :param str domain: Domain where the target Nominatim service
            is hosted.

        :param str scheme:
            See :attr:`geopy.geocoders.options.default_scheme`.

        :param str user_agent:
            See :attr:`geopy.geocoders.options.default_user_agent`.

        :type ssl_context: :class:`ssl.SSLContext`
        :param ssl_context:
            See :attr:`geopy.geocoders.options.default_ssl_context`.

        :param callable adapter_factory:
            See :attr:`geopy.geocoders.options.default_adapter_factory`.

            .. versionadded:: 2.0
        """
        
        super().__init__(
            scheme=scheme,
            timeout=timeout,
            proxies=proxies,
            user_agent=user_agent,
            ssl_context=ssl_context,
            adapter_factory=adapter_factory
        )
        
        self.verbose = verbose
        self.client_id  = client_id
        self.client_secret = client_secret
        
        #print(f"domain: {domain}, : {self._DEFAULT_BEST_DOMAIN}")
        self.domain = domain.strip('/')
        
        
        
        
        
        
        if token:
            
            self.token = {'access_token':token}
            if self.verbose:
                print("setting parameter token")
            
        else:
            self.token = None
            #self.renew_token()
#        print(f"auth url: {authorization_url}")

            

        self.api_street  = "%s://%s%s" % (self.scheme, self.domain, self.street_path)
        self.api_address = "%s://%s%s" % (self.scheme, self.domain, self.address_path)
        self.api_city = "%s://%s%s" % (self.scheme, self.domain, self.city_path)

    def renew_token(self):
        
        client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=client, scope=self.scope)

        authorization_url = "%s://%s%s" % (self.scheme, self.domain, self.authorization_path)
        self.token = oauth.fetch_token(token_url=authorization_url, include_client_id=True, client_secret=self.client_secret)

        if self.verbose:
            print(self.token)

        
    def _construct_url(self, base_api, params):
        """
        Construct geocoding request url.
        The method can be overridden in Nominatim-based geocoders in order
        to extend URL parameters.

        :param str base_api: Geocoding function base address - self.api
            or self.reverse_api.

        :param dict params: Geocoding params.

        :return: string URL.
        """
        return "?".join((base_api, urlencode(params)))

    def _call_api(self, api_base, params, timeout, exactly_one=True):
        
        if self.token is None:
            self.renew_token()
            
        headers= {
            "BelGov-Trace-Id": self.belgov_trace_id,
            "Authorization": f"Bearer {self.token['access_token']}"  
        }
        
        url = self._construct_url(api_base, params)
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        
#         print(f"street url : {street_url}")
        callback = partial(self._parse_json, exactly_one=exactly_one)
        try :
            return self._call_geocoder(url, callback, headers=headers, timeout=timeout)
        except GeocoderAuthenticationFailure:
            print("Renew token...")
            self.renew_token()
            headers["Authorization"] =  f"Bearer {self.token['access_token']}"  
        
            return self._call_geocoder(url, callback, headers=headers, timeout=timeout)
            
            
        
    def geocode(
            self,
            query,
            *,
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
            limit=None,
            addressdetails=False,
            language=False,
            geometry=None,
            extratags=False,
            country_codes=None,
            viewbox=None,
            bounded=False,
            featuretype=None,
            namedetails=False,
            skip_house_number=False,
        
    ):
        """
        Return a location point by address.

        :param query: The address, query or a structured query
            you wish to geocode.

            For a structured query, provide a dictionary whose keys
            are one of: `street`, `city`, `county`, `state`, `country`, or
            `postalcode`. For more information, see Nominatim's
            documentation for `structured requests`:

                https://nominatim.org/release-docs/develop/api/Search

        :type query: dict or str

        :param bool exactly_one: Return one result or a list of results, if
            available.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :param int limit: Maximum amount of results to return from Nominatim.
            Unless exactly_one is set to False, limit will always be 1.

        :param bool addressdetails: If you want in *Location.raw* to include
            address details such as house_number, city_district, postcode, etc
            (in a structured form) set it to True

        :param str language: Preferred language in which to return results.
            Either uses standard
            `RFC2616 <http://www.ietf.org/rfc/rfc2616.txt>`_
            accept-language string or a simple comma-separated
            list of language codes.

        :param str geometry: If present, specifies whether the geocoding
            service should return the result's geometry in `wkt`, `svg`,
            `kml`, or `geojson` formats. This is available via the
            `raw` attribute on the returned :class:`geopy.location.Location`
            object.

        :param bool extratags: Include additional information in the result if available,
            e.g. wikipedia link, opening hours.

        :param country_codes: Limit search results
            to a specific country (or a list of countries).
            A country_code should be the ISO 3166-1alpha2 code,
            e.g. ``gb`` for the United Kingdom, ``de`` for Germany, etc.

        :type country_codes: str or list

        :type viewbox: list or tuple of 2 items of :class:`geopy.point.Point` or
            ``(latitude, longitude)`` or ``"%(latitude)s, %(longitude)s"``.

        :param viewbox: Prefer this area to find search results. By default this is
            treated as a hint, if you want to restrict results to this area,
            specify ``bounded=True`` as well.
            Example: ``[Point(22, 180), Point(-22, -180)]``.

        :param bool bounded: Restrict the results to only items contained
            within the bounding ``viewbox``.

        :param str featuretype: If present, restrict results to certain type of features.
            Allowed values: `country`, `state`, `city`, `settlement`.

        :param bool namedetails: If you want in *Location.raw* to include
            namedetails, set it to True. This will be a list of alternative names,
            including language variants, etc.

        :rtype: ``None``, :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.

        """
        
        # Part 1: get street ID: 
        
        
        street_res= self._call_api(self.api_street, {"name": query["street"], "postCode": query["postcode"]}, timeout)

        if street_res is None:
            if self.verbose:
                print(f"Did not get any street for '{query['street']}', '{query['postcode']}'")
            
            city_res= self._call_api(self.api_city, {"name": query["city"], "postCode": query["postcode"]}, timeout)
            if city_res:
                # print(city_res)
                city_res["precision"] = "city"
                city_name = coalesce(city_res["name"], ["fr", "nl", "de"])
                
                postcode = city_res["postCode"]
                return Location(f"{postcode} {city_name}", (0,0), city_res) 
            
            return None
        
        if self.verbose:
            print(f"Got streetId: '{street_res['id']}'")
        addr_res= self._call_api(self.api_address, {"streetId": street_res["id"], "houseNumber": query["housenumber"]}, timeout)
        
        
      
        if self.verbose:
            print("addr res: ", addr_res)
            
        if addr_res is not None:
            addr_res["precision"] = "building"
             
        else:
            addr_res= self._call_api(self.api_address, {"streetId": street_res["id"]}, timeout)
            if self.verbose:
                print("res without house number")
                print(addr_res)
            
            
            if addr_res is not None:
                addr_res["precision"] = "street"
            
                
                
        if addr_res is not None:
            street_name = coalesce(addr_res["hasStreetName"]["name"], ["fr", "nl", "de"])
            housenumber = addr_res["houseNumber"] if addr_res["precision"] == "building" else None
            city_name = coalesce(addr_res["hasMunicipality"]["name"], ["fr", "nl", "de"])
            part_city_name = coalesce(addr_res["hasPartOfMunicipality"]["name"], ["fr", "nl", "de"]) if "name" in addr_res["hasPartOfMunicipality"] else None
            postcode = addr_res["hasPostalInfo"]["postCode"]

            if "addressPosition" in addr_res:
                coords = addr_res["addressPosition"]["wgs84"]
            else: 
                coords = {'lat':0, 'long':0}
                addr_res["precision"] = "country"
            
            return Location(f"{street_name}, {housenumber if housenumber else ''}, {postcode} {city_name} {'('+part_city_name+')' if part_city_name else ''}", (coords['lat'], coords['long']), addr_res) 
        else:
            
            return None
            
      

    def _parse_code(self, place):
        # Parse each resource.
        
        
        if "items" not in place or len(place["items"]) == 0:
            return None
        
        #print(f"{self.street_path} in {place['self']} ?") 
        if "belgianAddress/v2/streets?" in place["self"]:
            res= place["items"][0]
            res = {"id": res["id"], "name": res["name"]}
            return res
        
        if "belgianAddress/v2/addresses?" in place["self"]:
            
            #print("place: ", place)
            
            res = place["items"][0]
            
            return res
        
        if "belgianAddress/v2/postalInfos?" in place["self"]:
            res = place["items"][0]
            
            return res
        
        print("Unkown response format!!")
        

    def _parse_json(self, places, exactly_one):
        if not places:
            return None

        if self.verbose:
            print(places)
            
        if isinstance(places, collections.abc.Mapping) and 'error' in places:
            
            if places['error'] == 'Unable to geocode':
                # no results in reverse
                return None
            else:
                raise GeocoderQueryError(places['error'])

        if not isinstance(places, collections.abc.Sequence):
            places = [places]
        if exactly_one:
            return self._parse_code(places[0])
        else:
            return [self._parse_code(place) for place in places]
        
        
        
        
        
