from django.db.models import Count
from rest_framework import viewsets, status, exceptions
from rest_framework.decorators import list_route
from rest_framework.response import Response
from .models import Comment, Thread
from .serializers import CommentSerializer
import utils
from utils.hash import pbkdf2_hash, sha1
from ws4redis.publisher import RedisPublisher
from ws4redis.redis_store import RedisMessage
from django.core.cache import cache
from rest_framework.renderers import JSONRenderer
import json


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    renderer_classes = (JSONRenderer, )

    def get_thread(self):
        uri = self.request.GET.get('uri')
        if not uri:
            raise exceptions.NotFound('uri not found')
        thread = Thread.objects.filter(uri=uri).first()
        if thread is None:
            thread = Thread(uri=uri, title=uri).save()
        return thread

    def create(self, request, *args, **kwargs):
        request.data['remote_addr'] = utils.anonymize(request.META.get('REMOTE_ADDR'))
        self.thread = self.get_thread()
        response = super(CommentViewSet, self).create(request, *args, **kwargs)
        response.set_cookie(str(response.data['id']), sha1(response.data['text']))
        response.set_cookie('isso-%i' % response.data['id'], sha1(response.data['text']))

        message = RedisMessage(json.dumps(response.data))
        RedisPublisher(facility='thread-%i' % self.thread.pk, broadcast=True).publish_message(message)
        return response

    def perform_create(self, serializer):
        serializer.validated_data['thread'] = self.thread
        serializer.save()

    def list(self, request, *args, **kwargs):
        uri = request.GET.get('uri')
        root_id = request.GET.get('parent')
        # nested_limit = request.GET.get('nested_limit', 0)

        queryset = self.get_queryset().filter(thread__uri=uri)

        if root_id is not None:
            root_list = queryset.filter(parent=root_id)
        else:
            root_list = queryset.filter(parent__isnull=True)

        parent_count = queryset.values('parent').annotate(total=Count('parent'))
        reply_counts = {item['parent']: item['total'] for item in parent_count}

        rv = {
            'id': root_id,
            'total_replies': root_list.count(),
            'hidden_replies': reply_counts.get(root_id, 0) - root_list.count(),
            'replies': self.get_serializer(root_list, many=True).data
        }

        if root_id is None:
            for comment in rv['replies']:
                if comment['id'] in reply_counts:
                    comment['total_replies'] = reply_counts.get(comment['id'], 0)
                    replies = self.get_serializer(queryset.filter(parent=comment['id']), many=True).data
                else:
                    comment['total_replies'] = 0
                    replies = []

                comment['hidden_replies'] = comment['total_replies'] - len(replies)
                comment['replies'] = replies

        return Response(rv)

    def destroy(self, request, *args, **kwargs):
        id = request.COOKIES.get(str(self.kwargs.get('pk')), None)
        if id is None:
            raise  exceptions.NotAuthenticated
        instance = self.get_object()

        if self.get_queryset().filter(parent=instance.id).exists():
            instance.mode = 4
            instance.text = ''
            instance.author = ''
            instance.website = ''
            instance.save()
            response = Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)
        else:
            instance.delete()
            response = Response(None, status=status.HTTP_200_OK)

        response.delete_cookie(id)
        response.delete_cookie('isso-%s' % id)
        return response

    @list_route(methods=['post'])
    def count(self, request, *args, **kwargs):
        return Response(self.get_queryset().filter(thread__uri=request.GET.get('uri')).count())

    @list_route()
    def thread(self, request, *args, **kwargs):
        """
        Get thread id
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        return Response(self.get_thread().pk)