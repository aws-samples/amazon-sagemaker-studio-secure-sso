// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

const xml2js = require('xml2js');
let decoder = require('saml-encoder-decoder-js'),
    parseString = require("xml2js").parseString,
    stripPrefix = require("xml2js").processors.stripPrefix;
const https = require('https');
const AWS = require('aws-sdk')


exports.handler = (event, context, callback) => {

    console.log(event.body)
    var samlResponse = event.body.split('&')[0]
    var saml = decode(samlResponse.split('=')[1]);

    decoder.decodeSamlPost(saml, (err, xmlResponse) => {

        if (err) {
            throw new Error(err);
        } else {
            parseString(xmlResponse, { tagNameProcessors: [stripPrefix] },
                function(err, result) {
                    if (err) {
                        callback(null, {
                            "statusCode": 400,
                            "headers": {},
                            "body": JSON.stringify(err['message']),
                            "isBase64Encoded": false
                        })
                        console.error(err['message'])
                    } else {

                        var attrs = result.Response.Assertion[0].AttributeStatement[0].Attribute
                        var domainId
                        var userId
                        attrs.forEach(attr => {
                            switch (attr.$.Name) {
                                case 'domain-id':
                                    console.log('DOMAIN: ' + attr.AttributeValue[0]._)
                                    domainId = attr.AttributeValue[0]._
                                    break;
                                case 'username':
                                    console.log('USER: ' + attr.AttributeValue[0]._)
                                    userId = attr.AttributeValue[0]._
                                    break;
                                default:
                                    console.log(`No Match`);
                            }
                        });
                        var sagemaker = new AWS.SageMaker({ apiVersion: '2017-07-24' });
                        var params = {
                            DomainId: domainId,
                            UserProfileName: userId,
                            ExpiresInSeconds: 5,
                        };

                        sagemaker.createPresignedDomainUrl(params, function(err, data) {
                            if (err) {
                                callback(null, {
                                    "statusCode": err['statusCode'],
                                    "headers": {},
                                    "body": JSON.stringify(err['message']),
                                    "isBase64Encoded": false
                                })
                                console.error(err['message'])
                            } else {
                                var url = data.AuthorizedUrl
                                var response = {
                                    "statusCode": 302,
                                    "headers": {
                                        "Location": url
                                    },
                                    "isBase64Encoded": false
                                };
                                callback(null, response)
                            }
                        });
                    }
                });
        }

    })


};

function encode(uri) {
    return encodeURIComponent(uri).replace(/'/g, "%27").replace(/"/g, "%22");
}

function decode(uri) {
    return decodeURIComponent(uri.replace(/\+/g, " "));
}