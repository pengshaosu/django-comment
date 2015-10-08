import datetime
from rest_framework import serializers, exceptions
from .models import Comment
from utils import pbkdf2_hash
from django.core.cache import cache

class CommentSerializer(serializers.ModelSerializer):

    created = serializers.FloatField(source='get_created_timestamp', read_only=True)
    modified = serializers.FloatField(source='get_modified_timestamp', allow_null=True, read_only=True)
    hash = serializers.SerializerMethodField(read_only=True)
    thread = serializers.PrimaryKeyRelatedField(read_only=True)

    def get_hash(self, instance):
        key = instance.email or instance.remote_addr
        val = cache.get(key)
        if val is None:
            val = pbkdf2_hash(key)
            cache.set(key, val)
        return val

    class Meta:
        model = Comment
        fields = ('id', 'parent', 'created', 'modified', 'mode', 'text', 'thread', 'hash', 'author', 'email', 'website',
                  'likes', 'dislikes')

